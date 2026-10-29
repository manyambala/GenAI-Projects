# Payment service runbook
## Symptoms
Gateway timeouts, elevated payment latency, or failed checkout requests.
## Possible causes
Provider latency, retry storms, or connection exhaustion.
## Diagnostic steps
Check service status, inspect gateway timeout logs, and correlate request IDs.
## Safe remediation steps
Pause retry amplification, validate provider health, and escalate provider latency.
## Escalation conditions
Escalate when payment failures affect multiple customers or persist beyond 15 minutes.
## Metadata
owner: payments; version: 1.0; sensitivity: internal
