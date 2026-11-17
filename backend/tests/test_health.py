import socket
import threading

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import make_settings


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def listening_port():
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()
    stop = threading.Event()

    def accept_loop():
        server.settimeout(0.1)
        while not stop.is_set():
            try:
                conn, _ = server.accept()
                conn.close()
            except OSError:
                continue

    thread = threading.Thread(target=accept_loop, daemon=True)
    thread.start()
    yield server.getsockname()[1]
    stop.set()
    thread.join()
    server.close()


def test_liveness(client: TestClient):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["service"] == "KogniSync API"
    assert body["environment"] == "local"


def test_readiness_without_dependencies_is_ready(client: TestClient):
    res = client.get("/api/v1/health/ready")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ready"
    statuses = {d["name"]: d["status"] for d in body["dependencies"]}
    assert statuses == {
        "postgres": "not_configured",
        "redis": "not_configured",
        "gemini": "not_configured",
    }


def test_readiness_reports_reachable_dependencies(listening_port: int):
    settings = make_settings(
        database_url=f"postgresql://u:p@127.0.0.1:{listening_port}/db",
        redis_url=f"redis://127.0.0.1:{listening_port}/0",
        gemini_api_key="test-key",
    )
    res = TestClient(create_app(settings)).get("/api/v1/health/ready")
    assert res.status_code == 200
    assert all(d["status"] == "ok" for d in res.json()["dependencies"])


def test_readiness_unreachable_dependency_returns_503_without_leaking_secrets():
    port = _free_port()
    settings = make_settings(
        database_url=f"postgresql://user:supersecret@127.0.0.1:{port}/db",
        gemini_api_key="gemini-secret-value",
    )
    res = TestClient(create_app(settings)).get("/api/v1/health/ready")
    assert res.status_code == 503
    body = res.json()
    assert body["status"] == "degraded"
    pg = next(d for d in body["dependencies"] if d["name"] == "postgres")
    assert pg == {"name": "postgres", "status": "error", "detail": "unreachable"}
    assert "supersecret" not in res.text
    assert "gemini-secret-value" not in res.text


def test_cors_allows_frontend_origin(client: TestClient):
    res = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    assert res.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_openapi_served(client: TestClient):
    assert client.get("/api/openapi.json").status_code == 200
