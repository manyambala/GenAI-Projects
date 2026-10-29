from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from app.config import settings
from app.database import AgentExecutionRow, SessionLocal

from app.agents.state import MultiAgentState


def started() -> float:
    return perf_counter()


def record_execution(
    state: MultiAgentState,
    agent_name: str,
    input_data: dict[str, Any],
    output_data: dict[str, Any],
    started_at: float,
    *,
    used_model: bool = False,
    mark_completed: bool = True,
    message: str | None = None,
) -> MultiAgentState:
    duration_ms = (perf_counter() - started_at) * 1000
    trace = state.setdefault("agent_trace", [])
    sequence_number = len(trace) + 1
    trace_item = {
        "sequence_number": sequence_number,
        "agent_name": agent_name,
        "status": "COMPLETED",
        "used_model": used_model,
        "duration_ms": round(duration_ms, 1),
        "output": output_data,
    }
    trace.append(trace_item)
    if mark_completed and agent_name not in state.setdefault("completed_agents", []):
        state["completed_agents"].append(agent_name)
    state.setdefault("events", []).append({
        "workflow_state": agent_name,
        "event_type": "agent_completed",
        "message": message or f"{agent_name} completed",
        "metadata": {
            "sequence_number": sequence_number,
            "used_model": used_model,
            "duration_ms": round(duration_ms, 1),
        },
    })
    with SessionLocal() as db:
        db.add(AgentExecutionRow(
            ticket_id=state["ticket_id"],
            run_id=state["run_id"],
            sequence_number=sequence_number,
            agent_name=agent_name,
            status="COMPLETED",
            input_json=input_data,
            output_json=output_data,
            model_name=settings.ollama_model if used_model else None,
            used_model=used_model,
            duration_ms=duration_ms,
            created_at=datetime.now(timezone.utc),
        ))
        db.commit()
    return state
