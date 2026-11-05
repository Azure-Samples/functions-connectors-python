# Office 365 Outlook triggers (Python)

Choose one of two apps. Both cover the same seven events and use the
same SDK types and handler code.

| Sample | Delivery |
| --- | --- |
| [Polling](./polling/README.md) | The Functions host receives events from the Connector Namespace polling endpoint using Microsoft Entra credentials. No public callback is needed. |
| [Webhook](./webhook/README.md) | The Connector Namespace sends events to the Functions connector callback, authenticated with the extension system key. |

Each folder includes its own infrastructure, dependencies, and deployment hooks.
Keep the parent `office365App/scripts` folder: both hooks use its Python helper.
Run `azd up` from the folder you choose. Use different azd environment names if you
deploy both apps, so they do not share or overwrite resources.

| Function | Connector operation | SDK binding |
| --- | --- | --- |
| `OnNewEmail` | `OnNewEmailV3` | `list[office365.GraphClientReceiveMessage]` |
| `OnFlaggedEmail` | `OnFlaggedEmailV4` | `list[office365.GraphClientReceiveMessage]` |
| `OnNewMentionMeEmail` | `OnNewMentionMeEmailV3` | `list[office365.GraphClientReceiveMessage]` |
| `OnNewCalendarEvent` | `CalendarGetOnNewItemsV3` | `list[office365.GraphCalendarEventClientReceive]` |
| `OnUpcomingEvent` | `OnUpcomingEventsV3` | `list[office365.GraphCalendarEventClientReceive]` |
| `OnCalendarUpdatedItems` | `CalendarGetOnUpdatedItemsV3` | `list[office365.GraphCalendarEventClientReceive]` |
| `OnSharedMailboxNewEmail` | `SharedMailboxOnNewEmailV2` | `list[office365.GraphClientReceiveMessage]` (opt-in) |

Six personal-mailbox/calendar sources run by default. A nonempty
`OFFICE365_SHARED_MAILBOX_ADDRESS` enables the seventh source; full mailbox access
is required. Select the actual connector calendar ID rather than relying on the
`Calendar` placeholder. New mail no longer filters to high importance.

Do not register `CalendarGetOnChangedItemsV3` (added, updated or deleted events):
the reference reports that preview subscription fails with missing `TABLE`.
Deprecated versions are not included. `CalendarGetOnUpdatedItemsV3` is the supported
modified-event operation, not a substitute name for the changed-items operation.

The polling decorators add `delivery_mode=func.DeliveryMode.POLL` and
`trigger_config_name="%<FunctionName>TriggerConfigName%"`. All other decorator
arguments, type annotations, and handler code match the webhook sample. Both set
`connection="ConnectorNamespace"`; the Python SDK requires it for Poll delivery.

## Python dependencies

| Python | Minimum `azure-functions` | Required setting |
| --- | --- | --- |
| 3.13 and newer | `2.4.0b1` | None |
| 3.12 and older (supported Functions versions) | `1.27.0b1` | `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1` |

The deployment templates use Python 3.14. Both templates and local settings
examples include the isolation setting, so it remains set if you change to Python
3.12. Both apps require `azurefunctions-extensions-connectors>=1.0.0b4` for typed
payloads. One received connector event can contain several emails or calendar
items; the typed list describes that payload, not a request for host-level batching.

Handlers log only the function name and item count, not subjects, addresses,
organizers, dates, attachments or body content. Delivery is at least once; add
deduplication before using non-idempotent actions. Test with a test mailbox and
delete resources with `azd down --purge` when finished.

## Reference and language differences

The original Python samples followed .NET PR 8, commit
`768c426` (five events). This refresh follows local .NET PR 10 through
`d3f569a0aeae03df77fd071b362737f992917acc`, including its final polling-state
preservation change. It ports event coverage, configuration, identity, resource
access, local settings, callbacks, consent and setup guidance.

- Python uses existing extension item wrappers and lists, not .NET generated
	operation-envelope classes. SDK trigger metadata confirms the shared-mailbox
	and modified-event payloads use the same item types as the original events.
	No new model is invented. For a future event without a supported wrapper, use
	`str` and parse at the handler boundary rather than inventing an annotation.
- Python retains FC1, runtime 3.14, the dependency markers above and isolation `1`.
	`FUNCTIONS_WORKER_RUNTIME=python` belongs only in local settings, not FC1 settings.
- Resource creation now uses system-assigned identity. A separate function-access
	module grants host/deployment Blob Data Owner, Queue Data Contributor, Table Data
	Contributor and Monitoring Metrics Publisher roles after the identity exists.
	Polling also grants connection access to the app and developer. Webhooks use the
	extension system key and do not need app connection access to receive callbacks.
- Do not copy .NET NuGet packages, Program startup, isolated-worker runtime, or
	.NET worker telemetry code. Python keeps its host logging and preview bundle.
- Both PowerShell and POSIX hooks call a standard-library Python helper. Unlike
	the .NET scripts, these hooks do not require `jq` or .NET JSON APIs. Private JSON
	files avoid shell quoting and keep callback keys out of CLI arguments and logs;
	files are removed on success and failure. Unix files use mode 600 inside a mode
	700 directory; Windows uses the current user's temporary-directory ACLs.
- Local callback keys remain explicit options; do not put real keys in shell
	history, CI command logging or transcripts. The hook prints an OAuth consent
	link only when authorization is needed; treat that link as sensitive too.

Provisioning/build success is not proof of real event delivery. Calendar and
mailbox permissions, regional preview availability, OAuth consent and connector
source delays still need live verification. This refresh was validated offline.

## References

- [Office 365 Outlook connector](https://learn.microsoft.com/connectors/office365/)
- [Operations to Functions signature mapping](https://github.com/Azure/azure-functions-connector-extension/blob/main/docs/operations-functions-match.md)