from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.agents.workflow import build_graph, run_agent
from app.backup import create_backup, list_backups
from app.database import AgentExecutionRow, ApprovalRow, ResolutionRow, SessionLocal, TicketRow
from app.main import app
from app.config import settings
from app.rag.retriever import retrieve
from app.tools.mock_tools import check_service_status, find_runbook, get_recent_incidents, request_sensitive_action, search_logs


def test_tools_and_rag():
    assert check_service_status("payment")["status"] == "degraded"
    assert search_logs("payment")["entries"]
    assert "runbook_title" in find_runbook("payment")
    assert get_recent_incidents("payment")["previous_incidents"]
    assert retrieve("payment timeout")


def test_sensitive_action_requires_approval():
    assert request_sensitive_action("restart service")["requires_approval"] is True


def test_daily_log_file_contains_request():
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "daily-log-test"})
    assert response.status_code == 200
    log_date = datetime.now(ZoneInfo(settings.log_timezone)).date().isoformat()
    log_path = Path(settings.log_dir) / f"helpflow_{log_date}.log"
    assert log_path.exists()
    log_text = log_path.read_text(encoding="utf-8")
    assert "request_id=daily-log-test" in log_text
    assert "method=GET path=/health status=200" in log_text


def test_graph_nodes():
    assert set(build_graph().nodes) - {"__start__", "__end__"} == {
        "supervisor_agent", "triage_agent", "knowledge_agent", "diagnostic_agent",
        "evidence_verifier_agent", "resolution_agent", "policy_agent",
        "human_approval_agent", "finalize_response", "save_resolution",
    }


@pytest.mark.asyncio
async def test_multi_agent_workflow_and_execution_history():
    with SessionLocal() as db:
        ticket = TicketRow(
            title="Payment gateway timeout",
            description="Customers report repeated payment gateway timeouts",
            service_name="payment",
            priority="HIGH",
            status="OPEN",
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        ticket_id = ticket.id

    run_id = "multi-agent-test-run"
    state = await run_agent(ticket, run_id)
    completed = set(state["completed_agents"])
    assert {
        "triage_agent", "knowledge_agent", "diagnostic_agent",
        "evidence_verifier_agent", "resolution_agent", "policy_agent",
        "human_approval_agent",
    }.issubset(completed)
    assert state["approval"]["status"] == "PENDING"
    assert state["agent_trace"]

    with SessionLocal() as db:
        executions = db.query(AgentExecutionRow).filter_by(ticket_id=ticket_id, run_id=run_id).all()
    names = {item.agent_name for item in executions}
    assert "supervisor_agent" in names
    assert "triage_agent" in names
    assert "resolution_agent" in names
    assert "policy_agent" in names


def test_registration_login_and_role_authorization(monkeypatch):
    with TestClient(app) as client:
        assert client.post("/auth/register", json={"username": "admin", "password": "admin-password"}).status_code == 403
        assert client.post("/auth/register", json={"username": "admin", "password": "admin-password", "admin_token": "wrong-token"}).status_code == 403
        first = client.post("/auth/register", json={
            "username": "admin",
            "password": "admin-password",
            "admin_token": "test-admin-registration-token",
        })
        assert first.status_code == 201
        assert first.json()["role"] == "ADMIN"
        login = client.post("/auth/login", json={"username": "admin", "password": "admin-password"})
        assert login.status_code == 200
        admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        second_admin = client.post("/auth/register", json={
            "username": "second-admin",
            "password": "admin-password",
            "admin_token": "test-admin-registration-token",
        })
        assert second_admin.status_code == 201
        assert second_admin.json()["role"] == "ADMIN"
        assert client.post("/auth/register", json={
            "username": "invalid-admin",
            "password": "admin-password",
            "admin_token": "wrong-token",
        }).status_code == 403
        assert client.post("/users", headers=admin_headers, json={
            "username": "bypass-admin",
            "password": "admin-password",
            "role": "ADMIN",
        }).status_code == 422
        manager = client.post("/users", headers=admin_headers, json={"username": "manager", "password": "manager-password", "role": "SUPPORT_MANAGER"})
        agent = client.post("/users", headers=admin_headers, json={"username": "agent", "password": "agent-password", "role": "SUPPORT_AGENT"})
        other_agent = client.post("/users", headers=admin_headers, json={"username": "agent2", "password": "agent2-password", "role": "SUPPORT_AGENT"})
        assert manager.status_code == 201, manager.json()
        assert agent.status_code == 201, agent.json()
        assert other_agent.status_code == 201, other_agent.json()
        manager_login = client.post("/auth/login", json={"username": "manager", "password": "manager-password"})
        manager_headers = {"Authorization": f"Bearer {manager_login.json()['access_token']}"}
        agent_login = client.post("/auth/login", json={"username": "agent", "password": "agent-password"})
        agent_headers = {"Authorization": f"Bearer {agent_login.json()['access_token']}"}
        other_agent_login = client.post("/auth/login", json={"username": "agent2", "password": "agent2-password"})
        other_agent_headers = {"Authorization": f"Bearer {other_agent_login.json()['access_token']}"}
        # Keep ticket-scope assertions independent from the earlier registration/login assertions.
        admin_login = client.post("/auth/login", json={"username": "admin", "password": "admin-password"})
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
        admin_ticket = client.post("/tickets", headers=admin_headers, json={"title": "Admin-only ticket", "description": "Created by the administrator", "service_name": "identity", "priority": "LOW"})
        assert admin_ticket.status_code == 201, admin_ticket.json()
        ticket = client.post("/tickets", headers=agent_headers, json={"title": "Payment timeout", "description": "Customers report payment timeout", "service_name": "payment", "priority": "HIGH"})
        other_ticket = client.post("/tickets", headers=other_agent_headers, json={"title": "Search is degraded", "description": "Search requests are responding slowly", "service_name": "search", "priority": "MEDIUM"})
        assert ticket.status_code == 201
        assert ticket.json()["created_by"] == "agent"
        assert ticket.json()["created_by_role"] == "SUPPORT_AGENT"
        assert isinstance(ticket.json()["created_by_id"], int)
        assert client.post(f"/tickets/{ticket.json()['id']}/approve", headers=agent_headers, json={}).status_code == 403

        # Agents see and access only tickets they created.
        assert [item["id"] for item in client.get("/tickets", headers=agent_headers).json()] == [ticket.json()["id"]]
        assert client.get(f"/tickets/{other_ticket.json()['id']}", headers=agent_headers).status_code == 404
        assert client.post(f"/tickets/{admin_ticket.json()['id']}/run", headers=agent_headers).status_code == 404

        # Managers see agent/manager tickets for oversight, but not admin-created tickets.
        manager_ids = {item["id"] for item in client.get("/tickets", headers=manager_headers).json()}
        assert manager_ids == {ticket.json()["id"], other_ticket.json()["id"]}
        assert client.get(f"/tickets/{admin_ticket.json()['id']}", headers=manager_headers).status_code == 404

        # Administrators retain global visibility.
        admin_ids = {item["id"] for item in client.get("/tickets", headers=admin_headers).json()}
        assert {admin_ticket.json()["id"], ticket.json()["id"], other_ticket.json()["id"]}.issubset(admin_ids)


@pytest.mark.asyncio
async def test_end_to_end_approval_immutability_and_reopen(monkeypatch):
    async def fake_run(ticket, run_id):
        with SessionLocal() as db:
            db.add(ApprovalRow(ticket_id=ticket.id, run_id=run_id, action_description="Restart payment service", status="PENDING"))
            db.add(ResolutionRow(ticket_id=ticket.id, run_id=run_id, root_cause="Timeouts", recommendation="Validate the service", final_response="Needs review"))
            db.commit()
        return {"severity": "HIGH", "events": [{"workflow_state": "intake"}], "evidence": [{"source_type": "test", "source_name": "fixture", "content": "fact", "confidence": 1.0}], "recommendation": "Validate the service", "root_cause": "Timeouts", "approval": {"status": "PENDING", "action_description": "Restart payment service"}, "final_response": "Needs review"}

    monkeypatch.setattr("app.main.run_agent", fake_run)
    with TestClient(app) as client:
        admin_login = client.post("/auth/login", json={"username": "admin", "password": "admin-password"})
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
        ticket = client.post("/tickets", headers=admin_headers, json={"title": "Database outage", "description": "Database connection errors", "service_name": "database", "priority": "CRITICAL"}).json()
        run = client.post(f"/tickets/{ticket['id']}/run", headers=admin_headers)
        assert run.status_code == 200
        first_run_id = run.json()["run_id"]
        assert client.post(f"/tickets/{ticket['id']}/approve", headers=admin_headers, json={"decision_reason": "Reviewed evidence"}).status_code == 200
        assert client.post(f"/tickets/{ticket['id']}/reject", headers=admin_headers, json={}).status_code == 409
        assert client.post(f"/tickets/{ticket['id']}/run", headers=admin_headers).status_code == 409
        reopened = client.post(f"/tickets/{ticket['id']}/reopen", headers=admin_headers)
        assert reopened.status_code == 200
        assert reopened.json()["run_id"] != first_run_id
        second_run = client.post(f"/tickets/{ticket['id']}/run", headers=admin_headers)
        assert second_run.status_code == 200
        assert client.post(f"/tickets/{ticket['id']}/reject", headers=admin_headers, json={"decision_reason": "Not safe"}).status_code == 200
        detail = client.get(f"/tickets/{ticket['id']}", headers=admin_headers).json()
        assert [item["status"] for item in detail["approval_history"]] == ["APPROVED", "REJECTED"]
        assert len(detail["workflow_runs"]) == 2


def test_backup_utility():
    backups = list_backups()
    created = create_backup()
    assert created.endswith(".db")
    assert created in list_backups()
