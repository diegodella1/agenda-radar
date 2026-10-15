import pytest
from fastapi.testclient import TestClient

from agenda_radar.app import create_app
from agenda_radar.config import Settings
from agenda_radar.editorial import initialize_config
from agenda_radar.security import create_user


@pytest.fixture
def app(tmp_path):
    settings = Settings(
        data_dir=tmp_path / "data",
        secrets_dir=tmp_path / "secrets",
        backup_dir=tmp_path / "backups",
        cookie_secure=False,
    )
    application = create_app(settings)
    application.state.db.migrate()
    application.state.vault.initialize()
    with application.state.db.session() as session:
        initialize_config(session)
        create_user(session, "admin@example.test", "a-long-test-password")
        create_user(session, "editor@example.test", "a-long-test-password", "editor")
        create_user(session, "reader@example.test", "a-long-test-password", "reader")
    yield application
    application.state.db.engine.dispose()


@pytest.fixture
def client(app):
    client = TestClient(app)
    client.headers["X-Requested-With"] = "AgendaRadar"
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.test", "password": "a-long-test-password"},
    )
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf"]
    yield client
