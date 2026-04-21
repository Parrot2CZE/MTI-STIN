"""
Testy autentizace — přihlášení, odhlášení, ochrana rout.
"""

import pytest
from app import create_app
from app.auth import verify_password, is_logged_in


@pytest.fixture(autouse=True)
def app_ctx():
    app = create_app("testing")
    with app.app_context():
        yield


@pytest.fixture
def client():
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = False
    return app.test_client()


def test_verify_password_correct():
    assert verify_password("admin", "admin123") is True


def test_verify_password_wrong():
    assert verify_password("admin", "wrongpassword") is False


def test_verify_password_unknown_user():
    # Neznámý uživatel musí vrátit False, ne vyhazovat výjimku
    assert verify_password("ghost", "anything") is False


def test_login_redirects_on_success(client):
    r = client.post("/login", data={"username": "admin", "password": "admin123"},
                    follow_redirects=False)
    assert r.status_code == 302
    assert "/" in r.headers["Location"]


def test_login_shows_error_on_failure(client):
    r = client.post("/login", data={"username": "admin", "password": "bad"},
                    follow_redirects=True)
    assert r.status_code == 200
    assert "Nesprávné".encode("utf-8") in r.data or "Invalid".encode() in r.data


def test_protected_route_redirects_when_not_logged_in(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert "login" in r.headers["Location"]


def test_logs_api_returns_401_when_not_logged_in(client):
    r = client.get("/api/logs")
    assert r.status_code == 401


def test_logs_api_returns_200_when_logged_in(client):
    client.post("/login", data={"username": "admin", "password": "admin123"})
    r = client.get("/api/logs")
    assert r.status_code == 200
    assert r.get_json()["success"] is True


def test_logout_clears_session(client):
    client.post("/login", data={"username": "admin", "password": "admin123"})
    client.get("/logout")
    # Po odhlášení musí / přesměrovat na login
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302
