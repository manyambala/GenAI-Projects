from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentOutput(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class TriageResult(AgentOutput):
    issue_type: Literal["payment", "database", "authentication", "notification", "api"]
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    affected_service: str = Field(min_length=1, max_length=100)
    required_agents: list[Literal["knowledge_agent", "diagnostic_agent"]]
    reasoning_summary: str = Field(min_length=1, max_length=1000)


class DiagnosticPlan(AgentOutput):
    selected_tools: list[
        Literal["check_service_status", "search_logs", "find_runbook", "get_recent_incidents"]
    ]
    rationale: str = Field(min_length=1, max_length=1000)


class VerificationResult(AgentOutput):
    evidence_sufficient: bool
    root_cause: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: list[str]
    missing_evidence: list[str]


class ResolutionResult(AgentOutput):
    root_cause: str = Field(min_length=1, max_length=2000)
    recommendation: str = Field(min_length=1, max_length=4000)
    customer_response: str = Field(min_length=1, max_length=4000)
    requires_sensitive_action: bool


class PolicyResult(AgentOutput):
    decision: Literal["HUMAN_APPROVAL_REQUIRED", "SAFE_TO_PRESENT", "MANUAL_REVIEW"]
    risk: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    action_description: str = Field(min_length=1, max_length=2000)
    reason: str = Field(min_length=1, max_length=2000)
