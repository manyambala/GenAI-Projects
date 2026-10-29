from typing import Any, TypedDict


class MultiAgentState(TypedDict, total=False):
    ticket_id: int
    run_id: str
    title: str
    description: str
    service_name: str
    priority: str
    severity: str
    issue_type: str

    current_agent: str
    next_agent: str
    completed_agents: list[str]
    agent_trace: list[dict[str, Any]]
    supervisor_cycles: int
    max_supervisor_cycles: int

    triage_result: dict[str, Any]
    knowledge_result: dict[str, Any]
    diagnostic_result: dict[str, Any]
    verification_result: dict[str, Any]
    resolution_result: dict[str, Any]
    policy_result: dict[str, Any]

    events: list[dict]
    documents: list[dict]
    tool_results: dict[str, Any]
    evidence: list[dict]
    root_cause: str
    recommendation: str
    approval: dict
    final_response: str
