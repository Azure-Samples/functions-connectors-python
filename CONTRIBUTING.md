# Contributing

Keep changes focused on the affected connector and delivery mode. Each `polling`
or `webhook` folder is a standalone Function App; `kustoApp` is a handler scaffold,
and `genericApp` uses existing resources. Update the affected README when changing
setup, trigger behavior, or configuration.

## Set up a sample

Use Python 3.13 or newer. From the selected app folder, for example
`onedriveApp/polling`, create and activate a virtual environment:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

On PowerShell, activate with `.venv\Scripts\Activate.ps1` instead. For older
supported Python versions, follow the compatibility steps in the root README.
See the selected app's README for Functions Core Tools, Azurite, Azure CLI,
connector authorization, and local settings. Deployment with `azd up` creates
billable Azure resources; it is not required for the offline checks below.

## Offline validation

From the repository root in bash, use a separate virtual environment for the CI tools:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install --index-url https://pypi.org/simple -r .github/requirements-ci.txt
git ls-files -z -- '*.py' | xargs -0 -r python -m py_compile
python -m ruff check --select E9,F63,F7,F82 .
git ls-files -- '*requirements.txt' ':!:.github/requirements-ci.txt' | while read -r f; do
  python -m pip_audit --progress-spinner off --index-url https://pypi.org/simple -r "$f" || exit 1
done
git diff --check
```

These compile tracked Python files, run focused Ruff correctness rules, and
audit each sample's `requirements.txt` (including transitive dependencies) with
`pip-audit`. Public package downloads and vulnerability lookups require internet access.
Do not suppress baseline findings or upgrade unrelated sample dependencies just
to make a check pass; report them separately.

CI also runs CodeQL's Python `security-and-quality` suite with `build-mode: none`,
and dependency review of PR
changes (blocking high/critical findings). Only CodeQL's job grants
`security-events: write` to the automatically generated workflow token; checkout
does not persist credentials. No repository or organization secrets, Azure
credentials, deployment, or live connector calls are required.

CodeQL is advanced setup. If default setup is already enabled, a repository admin
must switch to advanced setup before this workflow can upload results.
GitHub's built-in secret scanning is managed separately in repository settings;
these workflows do not change those settings.

## Changes and reports

- Preserve authentication and avoid logging credentials or source payloads.
- Never commit `local.settings.json`, `.env`, `.azure`, virtual environments,
  generated packages, connection strings, callback keys, or real trigger inputs.
- Do not put account identifiers, tenant/subscription details, source URLs,
  payloads, or unredacted logs in issues or PRs. Use placeholders and synthetic data.
- Describe the affected sample, expected/actual behavior, and checks performed.
  Live event tests are manual and must follow that sample's README using test data;
  offline CI does not prove end-to-end delivery.
- Keep Learn metadata only on supported connector-specific standalone
  polling/webhook READMEs, not overview guides, generic apps, or the Kusto scaffold.
  Keep names/descriptions under 150 characters and unique `urlFragment` values
  under 100 characters ending in `python`.
- Record user-visible changes under **Unreleased** in `CHANGELOG.md`.

For sensitive security reports, use [Microsoft's security reporting process](https://www.microsoft.com/msrc)
instead of a public issue.
