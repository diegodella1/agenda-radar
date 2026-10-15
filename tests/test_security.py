import socket

import pytest
from fastapi.testclient import TestClient

from agenda_radar.network import FetchError, public_addresses


@pytest.mark.parametrize(
    "address", ["127.0.0.1", "169.254.169.254", "10.0.0.1", "::1", "192.168.1.1"]
)
def test_ssrf_blocks_private_addresses(monkeypatch, address):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [(0, 0, 0, "", (address, 80))])
    with pytest.raises(FetchError, match="ssrf_blocked"):
        public_addresses("http://example.com/feed")


def test_ssrf_rejects_credentials_and_scheme():
    for url in ["file:///etc/passwd", "http://user:password@example.com", "ftp://example.com"]:
        with pytest.raises(FetchError):
            public_addresses(url)


def test_csrf_and_editor_cannot_change_secrets(app):
    client = TestClient(app)
    assert client.get("/api/v1/events").status_code == 401
    assert (
        client.post("/api/v1/auth/login", json={"email": "x", "password": "x"}).status_code == 403
    )
    client.headers["X-Requested-With"] = "AgendaRadar"
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "editor@example.test", "password": "a-long-test-password"},
    )
    client.headers["X-CSRF-Token"] = login.json()["csrf"]
    assert (
        client.post(
            "/api/v1/admin/providers", json={"name": "openai", "value": "test-secret"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/admin/prompts", json={"template": "long enough text", "model": "model"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/editorial/decisions",
            json={"event_id": 1, "action": "follow"},
            headers={"X-CSRF-Token": "wrong"},
        ).status_code
        == 403
    )
    assert client.post("/api/v1/auth/logout", json={}).status_code == 200
    assert client.get("/api/v1/events").status_code == 401


def test_secrets_never_returned(client, app):
    assert (
        client.post(
            "/api/v1/admin/providers", json={"name": "openai", "value": "test-secret-value"}
        ).status_code
        == 200
    )
    assert "test-secret-value" not in client.get("/api/v1/admin/providers").text
    from agenda_radar.models import Secret

    with app.state.db.session() as session:
        assert "test-secret-value" not in session.get(Secret, "openai").encrypted
        assert app.state.vault.get(session, "openai") == "test-secret-value"


def test_login_rate_limit_persists_failed_attempts(app):
    client = TestClient(app, headers={"X-Requested-With": "AgendaRadar"})
    for _ in range(8):
        assert (
            client.post(
                "/api/v1/auth/login", json={"email": "admin@example.test", "password": "wrong"}
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "admin@example.test", "password": "wrong"}
        ).status_code
        == 429
    )
