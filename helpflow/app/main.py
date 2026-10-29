"""HelpFlow API: authenticated, auditable multi-agent support workflow."""

import json
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agents.workflow import run_agent
from app.auth import create_access_token, get_current_user, hash_password, require_roles, verify_password
from app.backup import create_backup
from app.config import settings
from app.database import (
    AgentExecutionRow, ApprovalRow, AuditLogRow, EventRow, EvidenceRow, ResolutionRow,
    SessionLocal, TicketRow, UserRow, WorkflowRunRow,
)
from app.logging_config import configure_app_logging
from app.models.schemas import ApprovalDecision, LoginRequest, TicketCreate, UserCreate, UserPatch, UserRegister

logger = configure_app_logging(settings.log_level, settings.log_dir, settings.log_timezone)

app = FastAPI(title="HelpFlow Local Agentic IT Support", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

_rate_window: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    client = request.client.host if request.client else "unknown"
    now = time.monotonic()
    bucket = _rate_window[client]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= settings.rate_limit_per_minute:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded", "request_id": request_id}, headers={"X-Request-ID": request_id})
    bucket.append(now)
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        logger.exception("Unhandled request failure request_id=%s path=%s", request_id, request.url.path)
        response = JSONResponse(status_code=500, content={"detail": "Unexpected server error", "request_id": request_id})
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"
    logger.info(
        "request_id=%s client=%s method=%s path=%s status=%s duration_ms=%.1f",
        request_id,
        client,
        request.method,
        request.url.path,
        status_code,
        elapsed_ms,
    )
    return response


def now() -> datetime:
    return datetime.now(timezone.utc)


def conflict(message: str):
    raise HTTPException(status_code=409, detail=message)


def ticket_or_404(db, ticket_id: int) -> TicketRow:
    row = db.get(TicketRow, ticket_id)
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return row


def ticket_for_user_or_404(db, ticket_id: int, user: UserRow) -> TicketRow:
    """Return a ticket only when it belongs to the caller's role scope.

    Administrators can access every ticket. Support agents can access only their
    own tickets. Support managers can access tickets created by support agents
    and support managers so they can perform human approval duties, while
    administrator-created tickets remain administrator-only.
    """
    row = ticket_or_404(db, ticket_id)
    if user.role == "ADMIN":
        return row
    creator = db.get(UserRow, row.created_by) if row.created_by is not None else None
    if user.role == "SUPPORT_AGENT" and row.created_by == user.id:
        return row
    if user.role == "SUPPORT_MANAGER" and creator and creator.role in {"SUPPORT_AGENT", "SUPPORT_MANAGER"}:
        return row
    # Use 404 instead of 403 so callers cannot enumerate tickets outside their scope.
    raise HTTPException(status_code=404, detail="Ticket not found")


def visible_tickets(db, user: UserRow):
    query = db.query(TicketRow)
    if user.role == "ADMIN":
        return query
    if user.role == "SUPPORT_AGENT":
        return query.filter(TicketRow.created_by == user.id)
    creator_ids = db.query(UserRow.id).filter(UserRow.role.in_(("SUPPORT_AGENT", "SUPPORT_MANAGER")))
    return query.filter(TicketRow.created_by.in_(creator_ids))


def audit(db, user_id: int | None, action: str, resource_type: str, resource_id: str, details: dict | None = None):
    db.add(AuditLogRow(user_id=user_id, action=action, resource_type=resource_type, resource_id=resource_id, details=json.dumps(details or {}, sort_keys=True)))


def user_view(user: UserRow) -> dict:
    return {"id": user.id, "username": user.username, "role": user.role, "is_active": user.is_active, "created_at": user.created_at, "updated_at": user.updated_at}


def serialize_ticket(row: TicketRow, db) -> dict:
    creator = db.get(UserRow, row.created_by) if row.created_by is not None else None
    return {
        "id": row.id, "title": row.title, "description": row.description, "service_name": row.service_name,
        "priority": row.priority, "severity": row.severity, "status": row.status,
        "created_by": creator.username if creator else "Unknown",
        "created_by_role": creator.role if creator else "Unknown",
        "created_by_id": row.created_by,
        "active_run_id": row.active_run_id, "created_at": row.created_at, "updated_at": row.updated_at,
    }


@app.get("/")
async def root():
    return {"service": "helpflow", "message": "HelpFlow Local Agentic IT Support API", "docs": "/docs", "health": "/health", "ready": "/ready"}


@app.get("/health")
async def health():
    try:
        with SessionLocal() as db:
            db.execute(__import__("sqlalchemy").text("SELECT 1"))
        return {"status": "ok", "service": "helpflow", "database": "sqlite", "llm_provider": "ollama-local"}
    except Exception:
        logger.exception("Health check failed")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@app.get("/ready")
async def ready():
    try:
        with SessionLocal() as db:
            db.execute(__import__("sqlalchemy").text("SELECT 1"))
        return {"status": "ready", "database": "available", "ollama_endpoint": settings.ollama_base_url}
    except Exception:
        raise HTTPException(status_code=503, detail="Service is not ready")


@app.post("/auth/register", status_code=201)
async def register(payload: UserRegister):
    with SessionLocal() as db:
        if not settings.admin_registration_token:
            raise HTTPException(status_code=503, detail="Admin registration token is not configured")
        if not secrets.compare_digest(payload.admin_token, settings.admin_registration_token):
            raise HTTPException(status_code=403, detail="Invalid admin registration token")
        if db.query(UserRow).filter_by(username=payload.username).first():
            raise HTTPException(status_code=409, detail="Username already exists")
        user = UserRow(username=payload.username, password_hash=hash_password(payload.password), role="ADMIN", is_active=True)
        db.add(user)
        db.flush()
        audit(db, user.id, "REGISTER", "user", str(user.id), {"role": "ADMIN"})
        db.commit()
        return user_view(user)


@app.post("/auth/login")
async def login(payload: LoginRequest):
    with SessionLocal() as db:
        user = db.query(UserRow).filter_by(username=payload.username).first()
        if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        token, expires_in = create_access_token(user)
        audit(db, user.id, "LOGIN", "user", str(user.id))
        db.commit()
        return {"access_token": token, "token_type": "bearer", "expires_in": expires_in, "user": user_view(user)}


@app.get("/auth/me")
async def me(user: UserRow = Depends(get_current_user)):
    return user_view(user)


@app.post("/users", status_code=201)
async def create_user(payload: UserCreate, user: UserRow = Depends(require_roles("ADMIN"))):
    with SessionLocal() as db:
        if db.query(UserRow).filter_by(username=payload.username).first():
            raise HTTPException(status_code=409, detail="Username already exists")
        created = UserRow(username=payload.username, password_hash=hash_password(payload.password), role=payload.role, is_active=True)
        db.add(created)
        db.flush()
        audit(db, user.id, "CREATE_USER", "user", str(created.id), {"role": created.role})
        db.commit()
        return user_view(created)


@app.get("/users")
async def list_users(_: UserRow = Depends(require_roles("ADMIN"))):
    with SessionLocal() as db:
        return [user_view(row) for row in db.query(UserRow).order_by(UserRow.id).all()]


@app.patch("/users/{user_id}")
async def patch_user(user_id: int, payload: UserPatch, user: UserRow = Depends(require_roles("ADMIN"))):
    with SessionLocal() as db:
        target = db.get(UserRow, user_id)
        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        if target.id == user.id and payload.is_active is False:
            raise HTTPException(status_code=409, detail="The active administrator cannot deactivate itself")
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(target, field, value)
        audit(db, user.id, "UPDATE_USER", "user", str(target.id), payload.model_dump(exclude_unset=True))
        db.commit()
        return user_view(target)


@app.post("/tickets", status_code=201)
async def create_ticket(payload: TicketCreate, user: UserRow = Depends(get_current_user)):
    with SessionLocal() as db:
        row = TicketRow(**payload.model_dump(), status="OPEN", created_by=user.id)
        db.add(row)
        db.flush()
        audit(db, user.id, "CREATE_TICKET", "ticket", str(row.id), {"service_name": row.service_name, "priority": row.priority})
        db.commit()
        db.refresh(row)
        return serialize_ticket(row, db)


@app.get("/tickets")
async def list_tickets(user: UserRow = Depends(get_current_user)):
    with SessionLocal() as db:
        return [serialize_ticket(row, db) for row in visible_tickets(db, user).order_by(TicketRow.id.desc()).all()]


def _approval_view(approval: ApprovalRow | None) -> dict | None:
    if not approval:
        return None
    return {"id": approval.id, "run_id": approval.run_id, "status": approval.status, "approved_by": approval.approved_by, "decision_reason": approval.decision_reason, "action_description": approval.action_description, "created_at": approval.created_at, "updated_at": approval.updated_at}


def _agent_execution_view(item: AgentExecutionRow) -> dict:
    return {
        "id": item.id,
        "run_id": item.run_id,
        "sequence_number": item.sequence_number,
        "agent_name": item.agent_name,
        "status": item.status,
        "used_model": item.used_model,
        "model_name": item.model_name,
        "duration_ms": round(item.duration_ms, 1),
        "input": item.input_json,
        "output": item.output_json,
        "created_at": item.created_at,
    }


@app.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: int, user: UserRow = Depends(get_current_user)):
    with SessionLocal() as db:
        row = ticket_for_user_or_404(db, ticket_id, user)
        runs = db.query(WorkflowRunRow).filter_by(ticket_id=ticket_id).order_by(WorkflowRunRow.created_at).all()
        approvals = db.query(ApprovalRow).filter_by(ticket_id=ticket_id).order_by(ApprovalRow.id).all()
        resolutions = db.query(ResolutionRow).filter_by(ticket_id=ticket_id).order_by(ResolutionRow.id).all()
        evidence = db.query(EvidenceRow).filter_by(ticket_id=ticket_id).order_by(EvidenceRow.id).all()
        agent_executions = db.query(AgentExecutionRow).filter_by(ticket_id=ticket_id).order_by(AgentExecutionRow.id).all()
        return {
            **serialize_ticket(row, db),
            "workflow_runs": [{"run_id": run.id, "status": run.status, "created_at": run.created_at, "started_at": run.started_at, "completed_at": run.completed_at, "created_by": run.created_by} for run in runs],
            "evidence": [{"id": item.id, "run_id": item.run_id, "source_type": item.source_type, "source_name": item.source_name, "content": item.content, "confidence": item.confidence, "created_at": item.created_at} for item in evidence],
            "agent_executions": [_agent_execution_view(item) for item in agent_executions],
            "approval": _approval_view(approvals[-1] if approvals else None),
            "approval_history": [_approval_view(item) for item in approvals],
            "resolutions": [{"id": item.id, "run_id": item.run_id, "root_cause": item.root_cause, "recommendation": item.recommendation, "final_response": item.final_response, "created_at": item.created_at} for item in resolutions],
        }


@app.get("/tickets/{ticket_id}/runs")
async def ticket_runs(ticket_id: int, user: UserRow = Depends(get_current_user)):
    with SessionLocal() as db:
        ticket_for_user_or_404(db, ticket_id, user)
        return [{"run_id": run.id, "ticket_id": run.ticket_id, "status": run.status, "created_at": run.created_at, "started_at": run.started_at, "completed_at": run.completed_at, "created_by": run.created_by} for run in db.query(WorkflowRunRow).filter_by(ticket_id=ticket_id).order_by(WorkflowRunRow.created_at).all()]


@app.get("/tickets/{ticket_id}/events")
async def events(ticket_id: int, user: UserRow = Depends(get_current_user)):
    with SessionLocal() as db:
        ticket_for_user_or_404(db, ticket_id, user)
        return [{"id": event.id, "run_id": event.run_id, "workflow_state": event.workflow_state, "event_type": event.event_type, "message": event.message, "metadata": event.metadata_json, "created_at": event.created_at} for event in db.query(EventRow).filter_by(ticket_id=ticket_id).order_by(EventRow.id).all()]


@app.get("/tickets/{ticket_id}/agent-executions")
async def agent_executions(ticket_id: int, user: UserRow = Depends(get_current_user)):
    with SessionLocal() as db:
        ticket_for_user_or_404(db, ticket_id, user)
        rows = db.query(AgentExecutionRow).filter_by(ticket_id=ticket_id).order_by(AgentExecutionRow.id).all()
        return [_agent_execution_view(item) for item in rows]


@app.post("/tickets/{ticket_id}/run")
async def run_ticket(ticket_id: int, user: UserRow = Depends(get_current_user)):
    with SessionLocal() as db:
        row = ticket_for_user_or_404(db, ticket_id, user)
        if row.status == "RUNNING":
            conflict("Ticket is already running.")
        if row.status == "WAITING_APPROVAL":
            return {"ticket_id": ticket_id, "run_id": row.active_run_id, "status": row.status, "message": "Existing active workflow run returned."}
        if row.status == "APPROVED":
            conflict("Ticket is already approved. Reopen it to start a new run.")
        if row.status == "REJECTED":
            conflict("Ticket is rejected. Reopen it to start a new run.")
        run = db.get(WorkflowRunRow, row.active_run_id) if row.active_run_id else None
        if not run or run.status != "OPEN":
            run = WorkflowRunRow(id=str(uuid4()), ticket_id=ticket_id, status="OPEN", created_by=user.id)
            db.add(run)
        run.status = "RUNNING"
        run.started_at = now()
        row.status = "RUNNING"
        row.active_run_id = run.id
        audit(db, user.id, "START_INVESTIGATION", "workflow_run", run.id, {"ticket_id": ticket_id})
        db.commit()
        run_id = run.id

    try:
        state = await run_agent(row, run_id)
    except Exception as exc:
        logger.exception("Agent run failed run_id=%s", run_id)
        with SessionLocal() as db:
            current = db.get(TicketRow, ticket_id)
            active = db.get(WorkflowRunRow, run_id)
            if current and active:
                current.status = "OPEN"
                current.active_run_id = None
                active.status = "FAILED"
                active.completed_at = now()
                audit(db, user.id, "INVESTIGATION_FAILED", "workflow_run", run_id, {"error_type": type(exc).__name__})
                db.commit()
        raise HTTPException(status_code=502, detail="Local agent investigation failed") from exc

    with SessionLocal() as db:
        current = db.get(TicketRow, ticket_id)
        active = db.get(WorkflowRunRow, run_id)
        current.status = "WAITING_APPROVAL"
        current.severity = state.get("severity")
        current.active_run_id = run_id
        active.status = "WAITING_APPROVAL"
        active.completed_at = now()
        audit(db, user.id, "INVESTIGATION_WAITING_APPROVAL", "workflow_run", run_id, {"ticket_id": ticket_id})
        db.commit()
    return {"ticket_id": ticket_id, "run_id": run_id, "status": "WAITING_APPROVAL", "state": state}


@app.post("/tickets/{ticket_id}/reopen")
async def reopen(ticket_id: int, user: UserRow = Depends(require_roles("SUPPORT_MANAGER", "ADMIN"))):
    with SessionLocal() as db:
        row = ticket_for_user_or_404(db, ticket_id, user)
        if row.status in ("RUNNING", "WAITING_APPROVAL"):
            conflict("Ticket is active. Finish or reject the current run before reopening.")
        if row.status == "OPEN":
            return {"ticket_id": ticket_id, "status": "OPEN", "message": "Ticket is already open; no new run created."}
        run = WorkflowRunRow(id=str(uuid4()), ticket_id=ticket_id, status="OPEN", created_by=user.id)
        db.add(run)
        row.status = "OPEN"
        row.active_run_id = run.id
        audit(db, user.id, "REOPEN_TICKET", "ticket", str(ticket_id), {"new_run_id": run.id})
        db.commit()
        return {"ticket_id": ticket_id, "status": "OPEN", "run_id": run.id, "message": "Ticket reopened. Start the new run explicitly."}


def _decision(ticket_id: int, payload: ApprovalDecision, user: UserRow, decision: str):
    with SessionLocal() as db:
        row = ticket_for_user_or_404(db, ticket_id, user)
        if row.status != "WAITING_APPROVAL":
            conflict("Ticket is not waiting for approval.")
        run = db.get(WorkflowRunRow, row.active_run_id) if row.active_run_id else None
        approval = db.query(ApprovalRow).filter_by(ticket_id=ticket_id, run_id=run.id if run else None).order_by(ApprovalRow.id.desc()).first() if run else None
        if not approval:
            raise HTTPException(status_code=404, detail="Pending approval not found")
        if approval.status != "PENDING":
            conflict("Approval decision is already final.")
        approval.status = decision
        approval.approved_by = user.username
        approval.decision_reason = payload.decision_reason or None
        approval.updated_at = now()
        row.status = decision
        audit(db, user.id, decision, "approval_request", str(approval.id), {"ticket_id": ticket_id, "run_id": run.id, "reason": payload.decision_reason})
        db.commit()
        return {"ticket_id": ticket_id, "run_id": run.id, "status": decision, "approved_by": user.username, "message": "Decision recorded; no external action was executed."}


@app.post("/tickets/{ticket_id}/approve")
async def approve(ticket_id: int, payload: ApprovalDecision, user: UserRow = Depends(require_roles("SUPPORT_MANAGER", "ADMIN"))):
    return _decision(ticket_id, payload, user, "APPROVED")


@app.post("/tickets/{ticket_id}/reject")
async def reject(ticket_id: int, payload: ApprovalDecision, user: UserRow = Depends(require_roles("SUPPORT_MANAGER", "ADMIN"))):
    return _decision(ticket_id, payload, user, "REJECTED")


@app.get("/audit-logs")
async def audit_logs(_: UserRow = Depends(require_roles("ADMIN"))):
    with SessionLocal() as db:
        return [{"id": row.id, "user_id": row.user_id, "action": row.action, "resource_type": row.resource_type, "resource_id": row.resource_id, "details": json.loads(row.details or "{}"), "created_at": row.created_at} for row in db.query(AuditLogRow).order_by(AuditLogRow.id.desc()).all()]


@app.post("/admin/backups")
async def backup(user: UserRow = Depends(require_roles("ADMIN"))):
    path = create_backup()
    with SessionLocal() as db:
        audit(db, user.id, "CREATE_BACKUP", "database", path, {})
        db.commit()
    return {"status": "created", "path": path}
