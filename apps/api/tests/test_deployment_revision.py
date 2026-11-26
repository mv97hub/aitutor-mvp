from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient

from app.main import app
from app.harness import run_code_version


def test_operator_can_compare_the_running_code_and_database(monkeypatch):
    commit = "0123456789abcdef" * 2 + "01234567"
    monkeypatch.setenv("RENDER_GIT_COMMIT", commit)
    client = TestClient(app)
    response = client.get("/health/revision")
    assert response.status_code == 200
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    expected = ScriptDirectory.from_config(config).get_heads()
    assert response.json() == {"api_commit": commit, "database_revisions": expected}
    assert client.get("/health").json() == {"ok": True}

    monkeypatch.setenv("RENDER_GIT_COMMIT", "unrecognized-host-value")
    assert client.get("/health/revision").json()["api_commit"] is None
    for suffix in ("extra", " extra", "0123456789abcdef01234567"):
        monkeypatch.setenv("RENDER_GIT_COMMIT", commit + suffix)
        assert client.get("/health/revision").json()["api_commit"] is None
        assert run_code_version() == f"harness-1 {commit}"
