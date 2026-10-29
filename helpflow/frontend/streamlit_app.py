import os
from typing import Any

import requests
import streamlit as st

API = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")
st.set_page_config(page_title="HelpFlow", page_icon="🛠️", layout="wide")


def api_call(method: str, path: str, **kwargs) -> tuple[int, Any]:
    headers = kwargs.pop("headers", {})
    timeout = kwargs.pop("timeout", 90)
    if st.session_state.get("token"):
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    try:
        response = requests.request(method, f"{API}{path}", headers=headers, timeout=timeout, **kwargs)
        try:
            body = response.json()
        except ValueError:
            body = {"detail": response.text}
        if response.status_code == 401 and path != "/auth/login":
            st.session_state.token = None
            st.session_state.user = None
        return response.status_code, body
    except requests.RequestException as exc:
        return 599, {"detail": f"API unavailable: {exc}"}


def show_api_error(status: int, body: Any):
    st.error(f"Request failed ({status})")
    st.json(body)


def select_visible_ticket(key: str) -> int | None:
    """Select from the tickets the API permits the signed-in user to see."""
    status, tickets = api_call("GET", "/tickets")
    if status != 200:
        show_api_error(status, tickets)
        return None
    if not tickets:
        st.info("No tickets are available for your account. Submit a ticket first.")
        return None
    labels = {
        f"#{ticket['id']} · {ticket['title']} · {ticket['status']}": ticket["id"]
        for ticket in tickets
    }
    selected = st.selectbox("Ticket", list(labels), key=key)
    return labels[selected]


def load_ticket(ticket_id: int) -> dict[str, Any] | None:
    status, ticket = api_call("GET", f"/tickets/{ticket_id}")
    if status != 200:
        show_api_error(status, ticket)
        return None
    return ticket


for key, value in (("token", None), ("user", None), ("last_run", None), ("created_ticket", None)):
    st.session_state.setdefault(key, value)


def login_screen():
    st.title("🛠️ HelpFlow")
    st.caption("Local agentic IT support · Ollama · RAG · human approval")
    login_tab, register_tab = st.tabs(["Login", "Admin"])
    with login_tab:
        with st.form("login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", type="primary")
        if submitted:
            status, body = api_call("POST", "/auth/login", json={"username": username, "password": password})
            if status == 200:
                st.session_state.token = body["access_token"]
                st.session_state.user = body["user"]
                st.rerun()
            show_api_error(status, body)
    with register_tab:
        st.info("Registration creates an ADMIN account and always requires the configured admin token. Support agents and managers are created by an administrator and only need to log in.")
        with st.form("register"):
            username = st.text_input("New username")
            password = st.text_input("New password", type="password")
            admin_token = st.text_input("Admin registration token", type="password")
            submitted = st.form_submit_button("Create admin account")
        if submitted:
            status, body = api_call("POST", "/auth/register", json={"username": username, "password": password, "admin_token": admin_token})
            if status == 201:
                st.success("Account created. Login from the first tab.")
            else:
                show_api_error(status, body)


if not st.session_state.user:
    login_screen()
    st.stop()

user = st.session_state.user
role = user["role"]
st.sidebar.title("🛠️ HelpFlow")
st.sidebar.caption(f"{user['username']} · {role}")
if st.sidebar.button("Log out"):
    st.session_state.token = None
    st.session_state.user = None
    st.rerun()

pages = [
    "Submit Ticket",
    "Agent Investigation",
    "Ticket History",
    "Workflow History",
    "Evidence",
    "Resolutions",
]
if role == "ADMIN":
    pages += ["User Management", "Audit Log", "Backups"]
page = st.sidebar.radio("Workspace", pages)


if page == "Submit Ticket":
    st.title("Submit a support ticket")
    with st.form("ticket"):
        title = st.text_input("Ticket title", "Payment service is failing")
        description = st.text_area("Description", "Customers report payment gateway timeouts")
        service = st.text_input("Service name", "payment")
        priority = st.selectbox("Priority", ["LOW", "MEDIUM", "HIGH", "CRITICAL"])
        submitted = st.form_submit_button("Create ticket", type="primary")
    if submitted:
        status, body = api_call("POST", "/tickets", json={"title": title, "description": description, "service_name": service, "priority": priority})
        if status == 201:
            st.session_state.created_ticket = body
            st.success(f"Created ticket #{body['id']}")
            st.json(body)
        else:
            show_api_error(status, body)
    if st.session_state.created_ticket:
        st.info(f"Latest ticket: #{st.session_state.created_ticket['id']}. Open Agent Investigation to run it.")


elif page == "Agent Investigation":
    st.title("Agent investigation")
    st.caption("Choose a ticket available to your role and account.")
    ticket_id = select_visible_ticket("investigation-ticket")
    if ticket_id is None:
        st.stop()
    ticket = load_ticket(ticket_id)
    if ticket is None:
        st.stop()
    st.caption(f"Current status: {ticket['status']} · active run: {ticket.get('active_run_id') or 'none'}")
    current_status = ticket["status"]
    run_disabled = current_status in {"RUNNING", "WAITING_APPROVAL", "APPROVED", "REJECTED"}
    if st.button("Run agent", type="primary", disabled=run_disabled):
        run_status, run_body = api_call("POST", f"/tickets/{ticket_id}/run", timeout=300)
        if run_status == 200:
            st.session_state.last_run = run_body
            st.success("Investigation finished and is waiting for human approval.")
            st.rerun()
        else:
            show_api_error(run_status, run_body)
    if current_status in {"APPROVED", "REJECTED"} and role in {"SUPPORT_MANAGER", "ADMIN"}:
        if st.button("Reopen ticket"):
            reopen_status, reopen_body = api_call("POST", f"/tickets/{ticket_id}/reopen")
            if reopen_status == 200:
                st.success("Ticket reopened with a new run ID.")
                st.rerun()
            show_api_error(reopen_status, reopen_body)
    approval = ticket.get("approval")
    if approval:
        st.warning(f"Approval status: {approval['status']} · {approval['action_description']}")
        if approval["status"] == "PENDING" and role in {"SUPPORT_MANAGER", "ADMIN"} and current_status == "WAITING_APPROVAL":
            reason = st.text_input("Decision reason", key=f"reason-{ticket_id}")
            left, right = st.columns(2)
            if left.button("Approve sensitive action", type="primary"):
                decision_status, decision_body = api_call("POST", f"/tickets/{ticket_id}/approve", json={"decision_reason": reason})
                if decision_status == 200:
                    st.success("Approval recorded.")
                    st.session_state.last_run = None
                    st.rerun()
                show_api_error(decision_status, decision_body)
            if right.button("Reject sensitive action"):
                decision_status, decision_body = api_call("POST", f"/tickets/{ticket_id}/reject", json={"decision_reason": reason})
                if decision_status == 200:
                    st.warning("Approval rejected.")
                    st.session_state.last_run = None
                    st.rerun()
                show_api_error(decision_status, decision_body)
        elif approval["status"] == "PENDING":
            st.info("Only SUPPORT_MANAGER or ADMIN can approve or reject sensitive actions.")


elif page == "Ticket History":
    st.title("Ticket history")
    st.caption("Administrators see all tickets. Other roles see only tickets in their role scope.")
    status, body = api_call("GET", "/tickets")
    if status == 200:
        st.dataframe(
            body,
            width=1200,
            hide_index=True,
            column_order=(
                "id", "title", "description", "service_name", "priority", "severity",
                "status", "created_by_role", "active_run_id", "created_at", "updated_at",
            ),
            column_config={
                "created_by_role": "Created By",
            },
        )
    else:
        show_api_error(status, body)


elif page == "Workflow History":
    st.title("Workflow history")
    ticket_id = select_visible_ticket("workflow-ticket")
    if ticket_id is None:
        st.stop()
    ticket = load_ticket(ticket_id)
    if ticket is None:
        st.stop()
    event_status, events = api_call("GET", f"/tickets/{ticket_id}/events")
    st.subheader("Runs")
    if ticket.get("workflow_runs"):
        st.dataframe(ticket["workflow_runs"], width=1200, hide_index=True)
    else:
        st.info("This ticket has no workflow runs yet.")
    st.subheader("Multi-agent execution history")
    if ticket.get("agent_executions"):
        st.dataframe(
            ticket["agent_executions"],
            width=1200,
            hide_index=True,
            column_order=(
                "sequence_number", "agent_name", "status", "used_model",
                "model_name", "duration_ms", "output", "created_at",
            ),
            column_config={
                "sequence_number": "Step",
                "agent_name": "Agent",
                "used_model": "Used Ollama",
                "duration_ms": "Duration (ms)",
            },
        )
    else:
        st.info("This ticket has no multi-agent execution history yet.")
    st.subheader("Workflow events")
    if event_status == 200 and events:
        st.dataframe(events, width=1200, hide_index=True)
    elif event_status == 200:
        st.info("This ticket has no workflow events yet.")
    else:
        show_api_error(event_status, events)
    st.subheader("Approval history")
    if ticket.get("approval_history"):
        st.dataframe(ticket["approval_history"], width=1200, hide_index=True)
    else:
        st.info("This ticket has no approval history yet.")


elif page == "Evidence":
    st.title("Evidence")
    ticket_id = select_visible_ticket("evidence-ticket")
    if ticket_id is None:
        st.stop()
    ticket = load_ticket(ticket_id)
    if ticket is None:
        st.stop()
    if ticket.get("evidence"):
        st.dataframe(ticket["evidence"], width=1200, hide_index=True)
    else:
        st.info("No evidence has been recorded. Run the agent investigation first.")


elif page == "Resolutions":
    st.title("Resolutions")
    ticket_id = select_visible_ticket("resolution-ticket")
    if ticket_id is None:
        st.stop()
    ticket = load_ticket(ticket_id)
    if ticket is None:
        st.stop()
    if ticket.get("resolutions"):
        st.dataframe(ticket["resolutions"], width=1200, hide_index=True)
    else:
        st.info("No resolution has been recorded. Run the agent investigation first.")


elif page == "User Management":
    st.title("User management")
    status, users = api_call("GET", "/users")
    if status == 200:
        st.dataframe(users, width=1200, hide_index=True)
    with st.form("new-user"):
        username = st.text_input("Username")
        password = st.text_input("Temporary password", type="password")
        new_role = st.selectbox("Role", ["SUPPORT_AGENT", "SUPPORT_MANAGER"])
        submitted = st.form_submit_button("Create user")
    if submitted:
        create_status, body = api_call("POST", "/users", json={"username": username, "password": password, "role": new_role})
        if create_status == 201:
            st.success("User created.")
            st.rerun()
        show_api_error(create_status, body)

elif page == "Audit Log":
    st.title("Audit log")
    status, body = api_call("GET", "/audit-logs")
    if status == 200:
        st.dataframe(body, width=1200, hide_index=True)
    else:
        show_api_error(status, body)


elif page == "Backups":
    st.title("SQLite backups")
    st.caption("Backups are local files and should be copied to protected storage in a real environment.")
    if st.button("Create backup", type="primary"):
        status, body = api_call("POST", "/admin/backups")
        if status == 200:
            st.success(f"Backup created: {body['path']}")
        else:
            show_api_error(status, body)
