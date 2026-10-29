import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, String, Text, Integer, DateTime, ForeignKey, JSON, Boolean, Float, inspect, text, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from app.config import settings

if settings.database_url.startswith("sqlite"):
    os.makedirs(os.path.dirname(settings.database_url.replace("sqlite:///", "")) or settings.data_dir, exist_ok=True)
connect_args = {"check_same_thread": False, "timeout": 30} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)


if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(30), default="SUPPORT_AGENT")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class TicketRow(Base):
    __tablename__ = "tickets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    service_name: Mapped[str] = mapped_column(String(100))
    priority: Mapped[str] = mapped_column(String(20))
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="OPEN")
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class EventRow(Base):
    __tablename__ = "agent_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"))
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    workflow_state: Mapped[str] = mapped_column(String(60))
    event_type: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class EvidenceRow(Base):
    __tablename__ = "evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"))
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_type: Mapped[str] = mapped_column(String(40))
    source_name: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class ApprovalRow(Base):
    __tablename__ = "approval_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"))
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action_description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class ResolutionRow(Base):
    __tablename__ = "resolutions"
    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"))
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    root_cause: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    final_response: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class WorkflowRunRow(Base):
    __tablename__ = "workflow_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"))
    status: Mapped[str] = mapped_column(String(30), default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AgentExecutionRow(Base):
    """Auditable record of one specialist or supervisor agent execution."""

    __tablename__ = "agent_executions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    sequence_number: Mapped[int] = mapped_column(Integer)
    agent_name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), default="COMPLETED")
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    used_model: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class AuditLogRow(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    resource_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(120))
    details: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


Base.metadata.create_all(engine)

def migrate_schema():
    """Apply additive, idempotent migrations without deleting legacy data."""
    Base.metadata.create_all(engine)
    additions = {
        'tickets': {'created_by': 'INTEGER', 'active_run_id': 'VARCHAR(36)'},
        'workflow_runs': {'started_at': 'DATETIME', 'created_by': 'INTEGER'},
        'agent_events': {'run_id': 'VARCHAR(36)'},
        'evidence': {'run_id': 'VARCHAR(36)'},
        'approval_requests': {'run_id': 'VARCHAR(36)', 'decision_reason': 'TEXT'},
        'resolutions': {'run_id': 'VARCHAR(36)'},
    }
    with engine.begin() as conn:
        for table, columns in additions.items():
            existing = {col['name'] for col in inspect(conn).get_columns(table)}
            for column, column_type in columns.items():
                if column not in existing:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {column_type}'))
        # Preserve legacy records by associating old rows with their latest run.
        # These updates are intentionally additive and never change approval status.
        conn.execute(text("UPDATE workflow_runs SET started_at = created_at WHERE started_at IS NULL"))
        conn.execute(text("""
            UPDATE tickets
            SET active_run_id = (
                SELECT workflow_runs.id FROM workflow_runs
                WHERE workflow_runs.ticket_id = tickets.id
                ORDER BY workflow_runs.created_at DESC LIMIT 1
            )
            WHERE active_run_id IS NULL AND status IN ('RUNNING', 'WAITING_APPROVAL')
        """))
        for table in ('agent_events', 'evidence', 'approval_requests', 'resolutions'):
            conn.execute(text(f"""
                UPDATE {table}
                SET run_id = (
                    SELECT workflow_runs.id FROM workflow_runs
                    WHERE workflow_runs.ticket_id = {table}.ticket_id
                    ORDER BY workflow_runs.created_at DESC LIMIT 1
                )
                WHERE run_id IS NULL
            """))

migrate_schema()
