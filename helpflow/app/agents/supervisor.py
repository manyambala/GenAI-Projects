from app.agents.state import MultiAgentState
from app.agents.tracking import record_execution, started


SPECIALISTS = (
    "triage_agent",
    "knowledge_agent",
    "diagnostic_agent",
    "evidence_verifier_agent",
    "resolution_agent",
    "policy_agent",
)


def run_supervisor(state: MultiAgentState) -> MultiAgentState:
    """Route work to bounded specialist agents and prevent delegation loops."""

    timer = started()
    state["current_agent"] = "supervisor_agent"
    state["supervisor_cycles"] = state.get("supervisor_cycles", 0) + 1
    max_cycles = state.get("max_supervisor_cycles", 12)
    completed = set(state.get("completed_agents", []))

    if state["supervisor_cycles"] > max_cycles:
        state["policy_result"] = {
            "decision": "MANUAL_REVIEW",
            "risk": "HIGH",
            "action_description": "Manually review the incomplete multi-agent investigation",
            "reason": "The supervisor reached its maximum routing cycles.",
        }
        next_agent = "human_approval_agent"
    elif "triage_agent" not in completed:
        next_agent = "triage_agent"
    else:
        required = set(state.get("triage_result", {}).get(
            "required_agents", ["knowledge_agent", "diagnostic_agent"]
        ))
        if "knowledge_agent" in required and "knowledge_agent" not in completed:
            next_agent = "knowledge_agent"
        elif "diagnostic_agent" in required and "diagnostic_agent" not in completed:
            next_agent = "diagnostic_agent"
        elif "evidence_verifier_agent" not in completed:
            next_agent = "evidence_verifier_agent"
        elif "resolution_agent" not in completed:
            next_agent = "resolution_agent"
        elif "policy_agent" not in completed:
            next_agent = "policy_agent"
        else:
            next_agent = "human_approval_agent"

    state["next_agent"] = next_agent
    return record_execution(
        state,
        "supervisor_agent",
        {"completed_agents": sorted(completed), "cycle": state["supervisor_cycles"]},
        {"next_agent": next_agent, "max_cycles": max_cycles},
        timer,
        mark_completed=False,
        message=f"Supervisor routed the investigation to {next_agent}",
    )


def route_from_supervisor(state: MultiAgentState) -> str:
    return state["next_agent"]
