from app.agents.state import MultiAgentState
from app.agents.tracking import record_execution, started
from app.rag.retriever import retrieve


def run_knowledge_agent(state: MultiAgentState) -> MultiAgentState:
    timer = started()
    query = f"{state['issue_type']} {state['description']}"
    documents = retrieve(query)
    result = {
        "query": query,
        "document_count": len(documents),
        "sources": [document["source_name"] for document in documents],
        "summary": (
            f"Retrieved {len(documents)} relevant local runbook document(s)."
            if documents else "No relevant runbook was found; manual knowledge review may be required."
        ),
    }
    state["documents"] = documents
    state["knowledge_result"] = result
    return record_execution(
        state, "knowledge_agent", {"query": query}, result, timer,
        message=result["summary"],
    )
