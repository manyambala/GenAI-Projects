# API HTTP 500 runbook
## Symptoms
HTTP 500 responses from an API endpoint.
## Possible causes
Unhandled exception, dependency failure, or invalid configuration.
## Diagnostic steps
Correlate request ID with application logs and service status.
## Safe remediation steps
Rollback only after approval; isolate the failing handler.
## Escalation conditions
Escalate when error rate is elevated.
## Metadata
owner: api; version: 1.0
