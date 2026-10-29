"""Supervisor-led multi-agent IT support workflow with human approval."""

from langgraph.graph import END, StateGraph

from app.agents.diagnostics import run_diagnostic_agent
from app.agents.human_approval import run_human_approval_agent
from app.agents.knowledge import run_knowledge_agent
from app.agents.policy import run_policy_agent
from app.agents.resolution import run_resolution_agent
from app.agents.state import MultiAgentState
from app.agents.supervisor import route_from_supervisor, run_supervisor
from app.agents.triage import run_triage_agent
from app.agents.verifier import run_evidence_verifier_agent
from app.database import ApprovalRow, EvidenceRow, EventRow, ResolutionRow, SessionLocal


def finalize_response(state: MultiAgentState) -> MultiAgentState:
    resolution = state["resolution_result"]
    verification = state["verification_result"]
    state["final_response"] = (
        f"Root cause hypothesis: {state['root_cause']}\n\n"
        f"Evidence confidence: {verification['confidence']:.0%}\n\n"
        f"Recommendation: {state['recommendation']}\n\n"
        f"Customer response: {resolution['customer_response']}\n\n"
        f"Approval status: {state['approval']['status']}"
    )
    state.setdefault("events", []).append({
        "workflow_state": "finalize_response",
        "event_type": "completed",
        "message": "Multi-agent final response prepared",
        "metadata": {},
    })
    return state


def save_resolution(state: MultiAgentState) -> MultiAgentState:
    state.setdefault("events", []).append({
        "workflow_state": "save_resolution",
        "event_type": "completed",
        "message": "Multi-agent investigation saved locally",
        "metadata": {"agent_execution_count": len(state.get("agent_trace", []))},
    })
    with SessionLocal() as db:
        for item in state.get("events", []):
            db.add(EventRow(
                ticket_id=state["ticket_id"], run_id=state["run_id"],
                workflow_state=item["workflow_state"], event_type=item["event_type"],
                message=item["message"], metadata_json=item.get("metadata", {}),
            ))
        for item in state.get("evidence", []):
            db.add(EvidenceRow(
                ticket_id=state["ticket_id"], run_id=state["run_id"],
                source_type=item["source_type"], source_name=item["source_name"],
                content=item["content"], confidence=item["confidence"],
            ))
        db.add(ApprovalRow(
            ticket_id=state["ticket_id"], run_id=state["run_id"],
            action_description=state["approval"]["action_description"], status="PENDING",
        ))
        db.add(ResolutionRow(
            ticket_id=state["ticket_id"], run_id=state["run_id"],
            root_cause=state["root_cause"], recommendation=state["recommendation"],
            final_response=state["final_response"],
        ))
        db.commit()
    return state


def build_graph():
    graph = StateGraph(MultiAgentState)
    graph.add_node("supervisor_agent", run_supervisor)
    graph.add_node("triage_agent", run_triage_agent)
    graph.add_node("knowledge_agent", run_knowledge_agent)
    graph.add_node("diagnostic_agent", run_diagnostic_agent)
    graph.add_node("evidence_verifier_agent", run_evidence_verifier_agent)
    graph.add_node("resolution_agent", run_resolution_agent)
    graph.add_node("policy_agent", run_policy_agent)
    graph.add_node("human_approval_agent", run_human_approval_agent)
    graph.add_node("finalize_response", finalize_response)
    graph.add_node("save_resolution", save_resolution)

    graph.set_entry_point("supervisor_agent")
    graph.add_conditional_edges(
        "supervisor_agent",
        route_from_supervisor,
        {
            "triage_agent": "triage_agent",
            "knowledge_agent": "knowledge_agent",
            "diagnostic_agent": "diagnostic_agent",
            "evidence_verifier_agent": "evidence_verifier_agent",
            "resolution_agent": "resolution_agent",
            "policy_agent": "policy_agent",
            "human_approval_agent": "human_approval_agent",
        },
    )
    for specialist in (
        "triage_agent", "knowledge_agent", "diagnostic_agent",
        "evidence_verifier_agent", "resolution_agent", "policy_agent",
    ):
        graph.add_edge(specialist, "supervisor_agent")
    graph.add_edge("human_approval_agent", "finalize_response")
    graph.add_edge("finalize_response", "save_resolution")
    graph.add_edge("save_resolution", END)
    return graph.compile()


GRAPH = build_graph()


async def run_agent(ticket, run_id: str):
    return await GRAPH.ainvoke({
        "ticket_id": ticket.id,
        "run_id": run_id,
        "title": ticket.title,
        "description": ticket.description,
        "service_name": ticket.service_name,
        "priority": ticket.priority,
        "completed_agents": [],
        "agent_trace": [],
        "events": [],
        "supervisor_cycles": 0,
        "max_supervisor_cycles": 12,
    })
