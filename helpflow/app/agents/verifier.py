from app.agents.ollama import ask_structured
from app.agents.prompts import VERIFIER_PROMPT
from app.agents.schemas import VerificationResult
from app.agents.state import MultiAgentState
from app.agents.tracking import record_execution, started


def _collect_evidence(state: MultiAgentState) -> list[dict]:
    evidence: list[dict] = []
    logs = state.get("tool_results", {}).get("search_logs", {}).get("result", {}).get("entries", [])
    for item in logs:
        evidence.append({"source_type": "tool", "source_name": "search_logs", "content": item.get("message", ""), "confidence": 0.9})
    status = state.get("tool_results", {}).get("check_service_status", {}).get("result", {})
    if status.get("status") not in (None, "unknown"):
        evidence.append({"source_type": "tool", "source_name": "check_service_status", "content": str(status), "confidence": 0.85})
    incidents = state.get("tool_results", {}).get("get_recent_incidents", {}).get("result", {}).get("previous_incidents", [])
    for incident in incidents[:3]:
        evidence.append({"source_type": "tool", "source_name": "get_recent_incidents", "content": str(incident), "confidence": 0.7})
    for document in state.get("documents", []):
        evidence.append({"source_type": "document", "source_name": document["source_name"], "content": document["content"][:500], "confidence": document["confidence"]})
    return evidence


async def run_evidence_verifier_agent(state: MultiAgentState) -> MultiAgentState:
    timer = started()
    evidence = _collect_evidence(state)
    log_evidence = [item for item in evidence if item["source_name"] == "search_logs"]
    fallback_root_cause = log_evidence[0]["content"] if log_evidence else "Insufficient evidence for a confirmed root cause"
    fallback = {
        "evidence_sufficient": bool(evidence),
        "root_cause": fallback_root_cause,
        "confidence": 0.75 if evidence else 0.2,
        "supporting_evidence": [item["content"][:200] for item in evidence[:5]],
        "missing_evidence": [] if evidence else ["Service status, logs, or relevant runbook evidence"],
    }
    prompt_evidence = [{**item, "content": item["content"][:600]} for item in evidence]
    result, used_model = await ask_structured(
        VERIFIER_PROMPT.format(evidence=prompt_evidence), fallback, VerificationResult
    )
    state["evidence"] = evidence
    state["verification_result"] = result
    state["root_cause"] = result["root_cause"]
    return record_execution(
        state, "evidence_verifier_agent", {"evidence_count": len(evidence)}, result,
        timer, used_model=used_model,
        message=f"Evidence verifier assessed {len(evidence)} item(s) at {result['confidence']:.0%} confidence",
    )
