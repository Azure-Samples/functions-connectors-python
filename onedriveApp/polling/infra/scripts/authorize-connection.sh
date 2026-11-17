#!/usr/bin/env bash
set -euo pipefail

# Runs before the triggers layer so Poll triggers are created enabled on an authorized connection.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/local-settings.sh"
jq() { connector_jq "$@"; }
az extension show --name connector-namespace --query name -o tsv >/dev/null
command -v jq >/dev/null || { echo 'jq is required.' >&2; exit 1; }

outputs=$(azd env get-values --output json | jq -ce '
  def required_string: type == "string" and test("\\S") and . != "null";
  if all(.AZURE_SUBSCRIPTION_ID, .resourceGroupName, .connectorNamespaceName, .connectorNamespaceConnectionName; required_string)
  then . else error("Base layer outputs are missing. Run azd provision base first.") end')
resourceGroupName=$(printf '%s' "$outputs" | jq -r '.resourceGroupName')
subscriptionId=$(printf '%s' "$outputs" | jq -r '.AZURE_SUBSCRIPTION_ID')
connectorNamespaceName=$(printf '%s' "$outputs" | jq -r '.connectorNamespaceName')
connectorNamespaceConnectionName=$(printf '%s' "$outputs" | jq -r '.connectorNamespaceConnectionName')

get_connection_status() {
  local status
  status=$(az connector-namespace connection show \
    --subscription "$subscriptionId" \
    -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
    -n "$connectorNamespaceConnectionName" --query 'properties.overallStatus' -o tsv) || return 1
  printf '%s\n' "${status%$'\r'}"
}

echo 'Authorizing OneDrive for Business connection...'
currentStatus=$(get_connection_status)
if [[ "$currentStatus" != 'Connected' ]]; then
  consentLink=""
  for attempt in 1 2 3 4 5; do
    consentLink=$(az connector-namespace connection list-consent-links \
      --subscription "$subscriptionId" \
      -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
      --connection-name "$connectorNamespaceConnectionName" \
      --parameters "[{parameterName:token,redirectUrl:'https://portal.azure.com'}]" \
      --query 'value[0].link' -o tsv 2>/dev/null) || consentLink=""
    consentLink="${consentLink%$'\r'}"
    if [[ -z "$consentLink" || "$consentLink" == 'null' ]]; then
      consentLink=$(az connector-namespace connection list-consent-links \
        --subscription "$subscriptionId" \
        -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
        --connection-name "$connectorNamespaceConnectionName" \
        --parameters "[{parameterName:token,redirectUrl:'https://portal.azure.com'}]" \
        --query 'link' -o tsv 2>/dev/null) || consentLink=""
    fi
    consentLink="${consentLink%$'\r'}"
    if [[ -n "$consentLink" && "$consentLink" != 'null' ]]; then break; fi
    if [[ "$attempt" != '5' ]]; then sleep 5; fi
  done
  if [[ -z "$consentLink" || "$consentLink" == 'null' ]]; then
    echo 'Failed to create consent link.' >&2
    exit 1
  fi
  echo "Sign in with the account that owns the OneDrive folder: $consentLink"
  if command -v xdg-open >/dev/null; then
    xdg-open "$consentLink" >/dev/null 2>&1 || true
  elif command -v open >/dev/null; then
    open "$consentLink" >/dev/null 2>&1 || true
  fi
  deadline=$((SECONDS + 300))
  while (( SECONDS < deadline )); do
    sleep 3
    currentStatus=$(get_connection_status)
    if [[ "$currentStatus" == 'Connected' ]]; then break; fi
  done
  if [[ "$currentStatus" != 'Connected' ]]; then
    echo 'Timed out waiting for the OneDrive connection to reach Connected status.' >&2
    exit 1
  fi
fi

"${PYTHON:-python}" "$SCRIPT_DIR/select_folder.py"
echo 'Done. The OneDrive connection is authorized; the triggers layer will create the 4 enabled Poll triggers.'
