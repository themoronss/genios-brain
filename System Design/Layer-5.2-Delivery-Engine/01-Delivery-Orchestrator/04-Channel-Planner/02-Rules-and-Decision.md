# Rules and decision

The concrete channel maps to one physics class and format:

| Channel | Class | Format |
|---|---|---|
| Slack / Teams | `chat` | Slack message / Teams action card |
| Webhook | `agent` transport class | signed webhook payload |
| Agent | `agent` | signed agent envelope |
| API | `in_app` | REST resource |
| Extension | `in_app` | inline suggestion |
| Application / mobile / dashboard / in-app | `in_app` | target-specific card |

Only chat can be marked interrupting, and only when the delivery class is critical, execution
confidence is at least 7,000 basis points, and current presence is not meeting/presenting/focus.
An escalation’s frozen interrupt hint can promote **delivery scheduling** to critical, but it
does not bypass these checks. Formatting is deterministic; an LLM may rewrite grounded copy
upstream but cannot select the route or policy.
