from app.agents.ollama import ask_structured
from app.agents.prompts import DIAGNOSTIC_PROMPT
from app.agents.schemas import DiagnosticPlan
from app.agents.state import MultiAgentState
from app.agents.tracking import record_execution, started
from app.tools.mock_tools import (
    check_service_status,
    find_runbook,
    get_recent_incidents,
    search_logs,
)


TOOLS = {
    "check_service_status": lambda state: check_service_status(state["service_name"]),
    "search_logs": lambda state: search_logs(state["service_name"]),
    "find_runbook": lambda state: find_runbook(state["issue_type"]),
    "get_recent_incidents": lambda state: get_recent_incidents(state["service_name"]),
}


def _safe_call(tool_name: str, state: MultiAgentState) -> dict:
    try:
        return {"ok": True, "result": TOOLS[tool_name](state)}
    except Exception as exc:
        return {"ok": False, "error_type": type(exc).__name__, "message": str(exc)}


async def run_diagnostic_agent(state: MultiAgentState) -> MultiAgentState:
    timer = started()
    context = {
        "service_name": state["service_name"],
        "issue_type": state["issue_type"],
        "severity": state["severity"],
        "description": state["description"],
    }
    fallback = {
        "selected_tools": list(TOOLS),
        "rationale": "Collect service status, logs, the relevant runbook, and recent incidents.",
    }
    plan, used_model = await ask_structured(
        DIAGNOSTIC_PROMPT.format(context=context), fallback, DiagnosticPlan
    )
    selected_tools = [name for name in plan["selected_tools"] if name in TOOLS]
    if not selected_tools:
        selected_tools = list(TOOLS)
    results = {name: _safe_call(name, state) for name in selected_tools}
    output = {
        "plan": {**plan, "selected_tools": selected_tools},
        "tool_results": results,
        "failures": [name for name, value in results.items() if not value["ok"]],
    }
    state["tool_results"] = results
    state["diagnostic_result"] = output
    return record_execution(
        state, "diagnostic_agent", context, output, timer, used_model=used_model,
        message=f"Diagnostic agent executed {len(selected_tools)} approved tool(s)",
    )
