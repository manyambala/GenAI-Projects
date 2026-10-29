from app.agents.ollama import ask_structured
from app.agents.prompts import POLICY_PROMPT
from app.agents.schemas import PolicyResult
from app.agents.state import MultiAgentState
from app.agents.tracking import record_execution, started


async def run_policy_agent(state: MultiAgentState) -> MultiAgentState:
    timer = started()
    resolution = state["resolution_result"]
    action_description = f"Apply the recommended {state['issue_type']} remediation to {state['service_name']}"
    fallback = {
        "decision": "HUMAN_APPROVAL_REQUIRED",
        "risk": "HIGH" if state["severity"] in {"HIGH", "CRITICAL"} else "MEDIUM",
        "action_description": action_description,
        "reason": "Operational remediation must be reviewed by an authorized human.",
    }
    result, used_model = await ask_structured(
        POLICY_PROMPT.format(resolution=resolution), fallback, PolicyResult
    )
    if resolution.get("requires_sensitive_action"):
        result["decision"] = "HUMAN_APPROVAL_REQUIRED"
        result["action_description"] = action_description
    state["policy_result"] = result
    return record_execution(
        state, "policy_agent", {"resolution": resolution}, result, timer,
        used_model=used_model, message=f"Policy agent decision: {result['decision']}",
    )
