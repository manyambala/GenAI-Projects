# Authentication runbook
## Symptoms
Slow login or elevated authentication errors.
## Possible causes
Slow identity queries, dependency latency, or exhausted worker capacity.
## Diagnostic steps
Check auth status and query-duration logs.
## Safe remediation steps
Review query plans and scale workers after approval.
## Escalation conditions
Escalate if all users cannot authenticate.
## Metadata
owner: identity; version: 1.0
