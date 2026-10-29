# HelpFlow Project Overview

## 1. Project introduction

HelpFlow is a local, supervisor-led multi-agent IT-support platform. Users create support tickets, and specialized agents collaborate through LangGraph using local runbooks, safe diagnostic tools, verified evidence, and an Ollama language model.

The platform includes authentication, role-based authorization, workflow history, evidence tracking, human approval, audit logging, backups, Docker Compose, and Kubernetes deployment.

## 2. Ticket workflow

A ticket normally follows this process:

```text
Ticket created
    ↓
Supervisor Agent routes work
    ↓
Triage Agent classifies issue and severity
    ↓
Knowledge Agent retrieves runbooks
    ↓
Diagnostic Agent selects and executes approved tools
    ↓
Evidence Verifier checks support and confidence
    ↓
Resolution Agent prepares a recommendation
    ↓
Policy Agent evaluates operational risk
    ↓
Manager or Admin approval
    ↓
Resolution and per-agent history recorded
```

The workflow is implemented in `app/agents/workflow.py`.

## 3. Application architecture

```text
Streamlit UI
    ↓
FastAPI API
    ├── JWT authentication and role authorization
    ├── SQLite database
    ├── LangGraph investigation workflow
    ├── RAG runbook retrieval
    ├── Safe diagnostic tools
    ├── Audit logs and backups
    └── Ollama local language model
```

## 4. FastAPI backend

The FastAPI backend provides APIs for:

- Authentication and Admin registration
- User management
- Ticket creation and retrieval
- Role-specific ticket visibility
- Agent investigations
- Approval and rejection
- Workflow history
- Evidence and resolutions
- Audit logs
- SQLite backups
- Health and readiness checks

The main backend file is `app/main.py`.

API documentation is available locally at:

```text
http://localhost:8000/docs
```

When using Kubernetes port-forwarding, it is available at:

```text
http://localhost:18000/docs
```

## 5. Streamlit frontend

The Streamlit frontend provides the following pages:

- Login
- Admin Registration
- Submit Ticket
- Agent Investigation
- Ticket History
- Workflow History
- Evidence
- Resolutions
- User Management
- Audit Log
- Backups

The frontend is implemented in `frontend/streamlit_app.py`.

## 6. LangGraph multi-agent workflow

LangGraph manages a Supervisor Agent and its specialist agents. The workflow contains these nodes:

- `supervisor_agent`
- `triage_agent`
- `knowledge_agent`
- `diagnostic_agent`
- `evidence_verifier_agent`
- `resolution_agent`
- `policy_agent`
- `human_approval_agent`
- `finalize_response`
- `save_resolution`

Specialists return their results to the Supervisor, which selects the next agent. Routing is bounded to prevent delegation loops. Every workflow run receives a unique run ID, and agent executions, evidence, approvals, and resolutions remain preserved.

## 7. Ollama local AI

HelpFlow uses Ollama instead of a cloud AI provider.

The currently configured model is:

```text
llama3.2:3b
```

In Docker Compose, the API connects to Ollama running on the Windows host through `host.docker.internal`.

In Kubernetes, Ollama runs as a StatefulSet. The model is stored in a persistent volume, and a model-loader Job automatically downloads the configured model.

If Ollama is unavailable, HelpFlow uses a deterministic fallback so the investigation does not completely fail.

## 8. RAG system

RAG means Retrieval-Augmented Generation. HelpFlow searches local IT runbooks and includes relevant information in the investigation.

The RAG system supports:

- Chroma vector search
- Local document embeddings
- Keyword-search fallback
- Local runbook documents

The RAG implementation is in `app/rag/`.

## 9. SQLite database

SQLite stores:

- Users
- Tickets
- Workflow runs
- Workflow events
- Agent executions and supervisor routing decisions
- Evidence
- Approval decisions
- Resolutions
- Audit logs

SQLite is configured with:

- WAL mode
- Foreign keys
- Busy timeout
- Additive migrations
- Persistent storage

The database implementation is in `app/database.py`.

Because SQLite is not suitable for multiple concurrent writers, the Kubernetes API uses one replica and the `Recreate` deployment strategy.

## 10. User roles

### Admin

- Registers using `ADMIN_REGISTRATION_TOKEN`
- Can register additional Admin accounts using the configured token
- Sees every ticket
- Creates Support Agent and Support Manager accounts
- Manages users
- Runs investigations
- Approves, rejects, and reopens tickets
- Views audit logs
- Creates backups

### Support Agent

- Uses an account created by an Admin
- Logs in without a registration token
- Creates tickets
- Sees only their own tickets
- Runs investigations on their tickets
- Views their workflow history, evidence, and resolutions

### Support Manager

- Uses an account created by an Admin
- Logs in without a registration token
- Sees tickets created by Support Agents and Support Managers
- Runs investigations
- Approves or rejects sensitive actions
- Reopens approved or rejected tickets

Authentication and authorization are implemented in `app/auth.py`.

## 11. Main Python libraries

| Library | Purpose |
|---|---|
| FastAPI | Backend REST API |
| Uvicorn | Runs the FastAPI application |
| Streamlit | Web user interface |
| SQLAlchemy | Database models and queries |
| Pydantic | Request and response validation |
| pydantic-settings | Environment-based application configuration |
| LangGraph | Agent investigation workflow and state machine |
| langchain-core | Common AI workflow components |
| ChromaDB | Vector database for runbook retrieval |
| sentence-transformers | Local document embeddings |
| HTTPX | Asynchronous HTTP communication |
| Requests | Communication from Streamlit to FastAPI |
| PyJWT | JWT access-token creation and validation |
| Argon2 | Secure password hashing |
| python-dotenv | Loads configuration from `.env` |
| python-multipart | Multipart and form request support |
| Pytest | Automated testing |
| pytest-asyncio | Tests asynchronous workflows |

Dependencies are listed in:

- `requirements.txt`
- `requirements.api.txt`
- `requirements.frontend.txt`

## 12. Diagnostic tools

The agent uses safe mock diagnostic tools such as:

- Searching service logs
- Checking service status
- Finding a runbook
- Retrieving recent incidents
- Requesting a sensitive action
- Drafting a customer response

These tools simulate real integrations without changing real production infrastructure.

The tools are implemented in `app/tools/mock_tools.py`.

## 13. Authentication

Admin registration requires the token configured in `.env`:

```env
ADMIN_REGISTRATION_TOKEN=your-admin-registration-token
```

Every successful registration creates an Admin account. Support Agent and Support Manager accounts are created by an authenticated Admin from the User Management page.

Passwords are hashed using Argon2. Login returns a signed JWT access token that is required for protected API operations.

## 14. Docker Compose deployment

Docker Compose runs:

- HelpFlow API
- Streamlit frontend
- SQLite persistent volume
- Backup volume
- Documents volume
- Vector-index volume

Ollama runs on the Windows host.

Build and start:

```powershell
cd "C:\Users\Lenovo\Documents\AI Projects\helpflow"
docker compose up -d --build
```

Check status:

```powershell
docker compose ps
docker compose logs -f
```

Open:

- UI: `http://localhost:8501`
- API: `http://localhost:8000`
- API documentation: `http://localhost:8000/docs`

Stop without deleting stored data:

```powershell
docker compose down
```

## 15. Kubernetes deployment

The Kubernetes setup contains:

- HelpFlow API Deployment
- HelpFlow frontend Deployment
- Ollama StatefulSet
- Ollama model-loader Job
- ClusterIP Services
- nginx Ingress
- SQLite persistent volume claim
- Ollama model persistent volume claim
- ConfigMap
- Kubernetes Secret
- Liveness and readiness probes

The manifests are stored in `k8s/`.

### Build images

```powershell
docker build -f Dockerfile.api -t helpflow-api:local .
docker build -f Dockerfile.frontend -t helpflow-frontend:local .
```

### Load images into Kind

```powershell
kind load docker-image helpflow-api:local helpflow-frontend:local --name kind
```

### Create namespace and secret

```powershell
kubectl apply -f k8s/namespace.yaml

kubectl create secret generic helpflow-secrets `
  -n helpflow `
  --from-literal=JWT_SECRET_KEY='replace-with-a-long-random-secret' `
  --from-literal=ADMIN_REGISTRATION_TOKEN='replace-with-an-admin-token'
```

### Validate and apply

```powershell
kubectl kustomize k8s
kubectl apply --dry-run=client -k k8s
kubectl apply -k k8s
```

### Check deployment

```powershell
kubectl get all,pvc,ingress -n helpflow
kubectl rollout status deployment/helpflow-api -n helpflow
kubectl rollout status deployment/helpflow-frontend -n helpflow
kubectl rollout status statefulset/ollama -n helpflow
kubectl wait --for=condition=complete job/ollama-model-loader -n helpflow --timeout=600s
kubectl exec -n helpflow ollama-0 -- ollama list
```

### Access the Kubernetes application

Use separate terminals:

```powershell
kubectl port-forward service/helpflow-frontend -n helpflow 18501:8501
```

```powershell
kubectl port-forward service/helpflow-api -n helpflow 18000:8000
```

Open:

- Kubernetes UI: `http://localhost:18501`
- Kubernetes API documentation: `http://localhost:18000/docs`

The alternate host ports allow Docker Compose and Kubernetes to run simultaneously.

## 16. Kubernetes recovery

Kubernetes automatically recreates API, frontend, and Ollama pods when an individual pod is deleted.

Test API recovery:

```powershell
kubectl delete pod -n helpflow -l app=helpflow-api
kubectl get pods -n helpflow -w
```

Test frontend recovery:

```powershell
kubectl delete pod -n helpflow -l app=helpflow-frontend
kubectl get pods -n helpflow -w
```

Test Ollama recovery:

```powershell
kubectl delete pod ollama-0 -n helpflow
kubectl get pods -n helpflow -w
```

SQLite data and Ollama models remain available because they are stored in persistent volumes.

## 17. Testing

The automated tests cover:

- Admin registration token validation
- Additional Admin registration
- Login
- Role authorization
- Admin user creation
- Per-user ticket visibility
- Workflow execution
- Approval and rejection
- Immutable approval decisions
- Reopening tickets
- RAG retrieval
- Diagnostic tools
- Backups

Run tests with:

```powershell
python -m pytest -q
```

## 18. Important limitations

- SQLite supports only a single API writer and should not be horizontally scaled.
- Ollama CPU inference can be slow without GPU support.
- The current diagnostic tools are safe mock tools rather than production integrations.
- Local files alone are not a complete disaster-recovery solution.
- The Kind Kubernetes cluster is intended for local development and demonstration.

## 19. Future improvements

For a larger production deployment, the project could migrate to:

- PostgreSQL for relational data
- Redis or another durable task queue
- Dedicated background workers
- Object storage for evidence and backups
- A managed identity provider
- Centralized monitoring and logging
- Real IT-service integrations
- GPU-enabled Ollama workers

## 20. Summary

HelpFlow demonstrates a complete local agentic IT-support workflow using FastAPI, Streamlit, LangGraph, Ollama, RAG, SQLite, Docker, and Kubernetes. It combines AI-assisted investigation with authentication, role-specific ticket access, evidence tracking, human approval, immutable workflow history, persistent storage, and automatic Kubernetes recovery.
