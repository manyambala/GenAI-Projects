from app.agents.ollama import ask_structured
from app.agents.prompts import TRIAGE_PROMPT
from app.agents.schemas import TriageResult
from app.agents.state import MultiAgentState
from app.agents.tracking import record_execution, started


def _fallback(state: MultiAgentState) -> dict:
    text = f"{state['title']} {state['description']}".lower()
    issue_type = (
        "payment" if "payment" in text
        else "database" if "database" in text or "connection" in text
        else "authentication" if "login" in text or "auth" in text
        else "notification" if "email" in text
        else "api"
    )
    severity = (
        "CRITICAL" if state.get("priority") == "CRITICAL" or "outage" in text or "all users" in text
        else "HIGH" if state.get("priority") == "HIGH" or "500" in text
        else "LOW" if state.get("priority") == "LOW"
        else "MEDIUM"
    )
    return {
        "issue_type": issue_type,
        "severity": severity,
        "affected_service": state["service_name"],
        "required_agents": ["knowledge_agent", "diagnostic_agent"],
        "reasoning_summary": f"Ticket classified as {issue_type} with {severity} severity.",
    }


async def run_triage_agent(state: MultiAgentState) -> MultiAgentState:
    timer = started()
    ticket = {
        "title": state["title"],
        "description": state["description"],
        "service_name": state["service_name"],
        "priority": state["priority"],
    }
    result, used_model = await ask_structured(
        TRIAGE_PROMPT.format(ticket=ticket), _fallback(state), TriageResult
    )
    state["triage_result"] = result
    state["issue_type"] = result["issue_type"]
    state["severity"] = result["severity"]
    return record_execution(
        state, "triage_agent", ticket, result, timer, used_model=used_model,
        message=f"Triage classified the ticket as {result['issue_type']} with {result['severity']} severity",
    )
