# FastAPI Internal Documentation

## 1. Getting Started with FastAPI
FastAPI is a modern, fast (high-performance), web framework for building APIs with Python 3.7+ based on standard Python type hints. Our organization has adopted FastAPI for all new Python-based microservices due to its speed, developer ergonomics, and out-of-the-box OpenAPI (Swagger) documentation.

To start a new project:
```python
from fastapi import FastAPI

app = FastAPI(title="My Internal API", version="1.0.0")

@app.get("/")
def read_root():
    return {"status": "healthy"}
```

## 2. Request Handling

### Path Parameters
You can declare path "parameters" or "variables" with the same syntax used by Python format strings:
```python
@app.get("/items/{item_id}")
def read_item(item_id: int):
    return {"item_id": item_id}
```
FastAPI will automatically validate that `item_id` is an integer.

### Query Parameters
When you declare other function parameters that are not part of the path parameters, they are automatically interpreted as "query" parameters.
```python
@app.get("/users/")
def get_users(skip: int = 0, limit: int = 10):
    return fake_db[skip : skip + limit]
```

### Request Body
Use Pydantic models to declare request bodies:
```python
from pydantic import BaseModel

class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None

@app.post("/items/")
def create_item(item: Item):
    return item
```

## 3. Dependency Injection System
FastAPI has a very powerful but intuitive Dependency Injection system. It is designed to be very simple to use, and to make it very easy for any developer to integrate other components with FastAPI.

```python
from fastapi import Depends

def common_parameters(q: str | None = None, skip: int = 0, limit: int = 100):
    return {"q": q, "skip": skip, "limit": limit}

@app.get("/items/")
def read_items(commons: dict = Depends(common_parameters)):
    return commons
```
Dependencies can be reused across multiple endpoints, ensuring DRY code.

## 4. Authentication
We use OAuth2 with JWT (JSON Web Tokens) for internal APIs. 

```python
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_current_user(token: str = Depends(oauth2_scheme)):
    user = decode_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return user

@app.get("/users/me")
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user
```
API Keys are also supported via `APIKeyHeader` for service-to-service communication.

## 5. Middleware
Middleware is a function that works with every request before it is processed by any specific path operation.

### CORS
To allow Cross-Origin Resource Sharing from our frontends:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://internal.dashboard.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Rate Limiting & Logging
We implement custom middleware for rate limiting and logging request latency and status codes.

## 6. Background Tasks
FastAPI allows you to define background tasks to be run after returning a response. This is useful for operations that need to happen after a request, but that the client doesn't really have to wait for.

```python
from fastapi import BackgroundTasks

def write_notification(email: str, message=""):
    with open("log.txt", mode="a") as email_file:
        content = f"notification for {email}: {message}\n"
        email_file.write(content)

@app.post("/send-notification/{email}")
async def send_notification(email: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(write_notification, email, message="some notification")
    return {"message": "Notification sent in the background"}
```

## 7. WebSocket Support
For real-time features, FastAPI supports WebSockets natively.
```python
from fastapi import WebSocket

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Message text was: {data}")
```

## 8. Testing
Testing is done using `pytest` and `httpx` via FastAPI's `TestClient`.

```python
from fastapi.testclient import TestClient
from myapp.main import app

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
```

## 9. Database Integration
We use SQLAlchemy for database operations. We recommend using the new 2.0 style async sessions.
Ensure you use connection pooling and handle session lifecycle correctly using dependencies.

## 10. Deployment
We deploy FastAPI apps in Kubernetes using Docker containers.
The standard setup uses Gunicorn as a process manager with Uvicorn workers.

```bash
gunicorn myapp.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## 11. Error Handling Best Practices
Do not leak internal errors to the client. Use FastAPI's `HTTPException` for expected errors (e.g., 404, 400).
For unexpected server errors (500), ensure you log the traceback but return a generic message to the client.

```python
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```
