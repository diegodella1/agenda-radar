import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from agenda_radar.app import create_app
from agenda_radar.bootstrap import prepare
from agenda_radar.config import Settings
from agenda_radar.editorial import initialize_config, publish_config
from agenda_radar.jobs import claim, enqueue
from agenda_radar.models import State, User
from agenda_radar.schemas import EditorialConfig


@pytest.fixture
def empty_app(tmp_path):
    app = create_app(
        Settings(data_dir=tmp_path / "data", secrets_dir=tmp_path / "secrets", cookie_secure=True)
    )
    app.state.db.migrate()
    app.state.vault.initialize()
    with app.state.db.session() as session:
        initialize_config(session)
    yield app
    app.state.db.engine.dispose()


def test_setup_single_use_expiry_and_https_login(empty_app):
    app = empty_app
    client = TestClient(
        app,
        base_url="https://mp.diegodella.ar",
        headers={
            "X-Requested-With": "AgendaRadar",
            "Origin": "https://mp.diegodella.ar",
        },
    )
    path = prepare(app.state.db, app.state.settings.secrets_dir)
    code = path.read_text().strip()
    assert path.stat().st_mode & 0o777 == 0o600
    payload = dict(code=code, email="first@example.test", password="long-setup-password")
    assert client.get("/setup").status_code == 200
    assert (
        client.post(
            "/api/v1/auth/setup", json=payload, headers={"Origin": "https://evil.test"}
        ).status_code
        == 403
    )
    assert client.post("/api/v1/auth/setup", json={**payload, "code": "x" * 43}).status_code == 422
    with app.state.db.session() as session:
        assert session.scalar(select(User.id)) is None
        state = session.get(State, "bootstrap")
        assert code not in str(state.value)
        state.value = {**state.value, "expires_at": time.time() - 1}
    assert client.post("/api/v1/auth/setup", json=payload).status_code == 422
    payload["code"] = prepare(app.state.db, app.state.settings.secrets_dir).read_text().strip()
    assert client.post("/api/v1/auth/setup", json=payload).status_code == 200
    assert not path.exists()
    assert client.post("/api/v1/auth/setup", json=payload).status_code == 422
    assert client.get("/setup", follow_redirects=False).status_code == 303
    login = client.post(
        "/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}
    )
    assert login.status_code == 200
    assert "Secure" in login.headers["set-cookie"]
    assert client.get("/api/v1/admin/readiness").json()["ready_for_pilot"] is False
    with pytest.raises(ValueError):
        prepare(app.state.db, app.state.settings.secrets_dir)


def test_pause_keeps_ingestion_pending_but_allows_backups(app):
    db = app.state.db
    with db.session() as session:
        publish_config(session, EditorialConfig(run_enabled=False), 1, "Pause test")
    poll_id = enqueue(db, "poll", {"source_id": 1}, "paused-poll")
    enqueue(db, "enrich", {}, "paused-enrich")
    backup_id = enqueue(db, "backup", {}, "backup")
    assert claim(db, "worker").id == backup_id
    assert claim(db, "worker") is None
    with db.session() as session:
        publish_config(session, EditorialConfig(run_enabled=True), 1, "Resume test")
    assert claim(db, "worker").id == poll_id


def test_production_redirects_http_to_canonical_https(empty_app):
    empty_app.state.settings.app_base_url = "https://mp.diegodella.ar"
    client = TestClient(empty_app, base_url="http://unexpected.example")
    response = client.get("/login?next=account", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "https://mp.diegodella.ar/login?next=account"
    assert client.get("/health/live").status_code == 200
    secure = TestClient(empty_app, base_url="https://mp.diegodella.ar")
    assert secure.get("/login").headers["Strict-Transport-Security"] == "max-age=31536000"
