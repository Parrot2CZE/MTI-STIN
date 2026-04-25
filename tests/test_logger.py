"""
Testy in-memory loggeru.
"""

import pytest
from app import create_app
from app.logger import get_logs, _LOG_BUFFER


@pytest.fixture(autouse=True)
def clear_logs():
    """Před každým testem vyprázdníme buffer, aby logy z jiných testů nekontaminovaly výsledky."""
    _LOG_BUFFER.clear()
    yield
    _LOG_BUFFER.clear()


def test_logs_initially_empty():
    assert get_logs() == []


def test_log_written_on_query():
    app = create_app("testing")
    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin123"})
        logs = get_logs()
        assert isinstance(logs, list)


def test_logs_endpoint_returns_list():
    app = create_app("testing")
    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin123"})
        r = client.get("/api/logs")
        assert r.status_code == 200
        data = r.get_json()
        assert "logs" in data
        assert isinstance(data["logs"], list)
