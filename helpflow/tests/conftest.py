import os
import shutil
import tempfile
from pathlib import Path

# Keep API tests isolated from the user's preserved local database.
_test_root = Path(tempfile.mkdtemp(prefix="helpflow-tests-"))
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = f"sqlite:///{(_test_root / 'helpflow.db').as_posix()}"
os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-with-32-bytes!!"
os.environ["ADMIN_REGISTRATION_TOKEN"] = "test-admin-registration-token"
os.environ["OLLAMA_MODEL"] = ""
os.environ["LOG_DIR"] = str(_test_root / "logs")
os.environ["RATE_LIMIT_PER_MINUTE"] = "10000"


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_test_root, ignore_errors=True)
