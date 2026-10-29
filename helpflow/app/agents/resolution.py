from app.agents.ollama import ask_structured
from app.agents.prompts import RESOLUTION_PROMPT
from app.agents.schemas import ResolutionResult
from app.agents.state import MultiAgentState
from app.agents.tracking import record_execution, started


async def run_resolution_agent(state: MultiAgentState) -> MultiAgentState:
    timer = started()
    verification = state["verification_result"]
    context = {"ticket": state["title"], "service_name": state["service_name"], "issue_type": state["issue_type"], "verification": verification}
    fallback = {
        "root_cause": verification["root_cause"],
        "recommendation": f"Follow the {state['issue_type']} runbook, validate {state['service_name']} service health, and escalate for manual review if the condition persists.",
        "customer_response": "The support team has investigated the issue and prepared a remediation plan for review.",
        "requires_sensitive_action": True,
    }
    result, used_model = await ask_structured(
        RESOLUTION_PROMPT.format(context=context), fallback, ResolutionResult
    )
    state["resolution_result"] = result
    state["root_cause"] = result["root_cause"]
    state["recommendation"] = result["recommendation"]
    return record_execution(
        state, "resolution_agent", context, result, timer, used_model=used_model,
        message="Resolution agent prepared an evidence-based recommendation",
    )
