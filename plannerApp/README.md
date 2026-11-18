# Planner connector triggers (Python)

Choose [polling](polling/README.md) (the host pulls events; no public endpoint) or [webhook](webhook/README.md) (the Connector Namespace calls the deployed app). Each folder is a standalone app; use a separate azd environment for each.

| Function | Connector operation | Required inputs |
| --- | --- | --- |
| `OnPlannerCompleteTask` | `OnCompleteTask_V3` | `groupId`, `id` (plan ID) |
| `OnPlannerNewTask` | `OnNewTask_V3` | `groupId`, `id` (plan ID) |
| `OnPlannerTaskAssignedToMe` | `OnTaskAssignedToMe_V2` | None; uses the signed-in user |

See the [Planner connector reference](https://learn.microsoft.com/connectors/planner/) for trigger inputs and payloads.
