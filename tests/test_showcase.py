from fastapi.testclient import TestClient

from agenda_radar.app import create_app
from agenda_radar.config import Settings


def test_showcase_needs_no_database_corpus_or_external_requests(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Showcase must not initialize a database or import news")

    monkeypatch.setattr("agenda_radar.db.Database.migrate", forbidden)
    settings = Settings(_env_file=None, data_dir=tmp_path / "data",
                        secrets_dir=tmp_path / "secrets",
                        demo_enabled=True, cookie_secure=False)
    app = create_app(settings)
    with TestClient(app) as client:
        for path in ("/demo/", "/demo/login", "/demo/events/1", "/demo/admin/config"):
            response = client.get(path)
            assert response.status_code == 200
            assert "showcase.js" in response.text
            assert response.headers["content-language"] == "en"
            assert "noindex" in response.headers["x-robots-tag"]
        assert client.post("/demo/api/v1/demo/news", json={}).status_code == 405
        assert client.get("/demo/unknown").status_code == 404
    assert not settings.database_path.exists()
    app.state.db.engine.dispose()


def test_locale_default_switch_persistence_and_invalid_values(app):
    app.state.settings.default_language = "en"
    with TestClient(app) as client:
        english = client.get("/home")
        assert '<html lang="en"' in english.text
        assert "Stop scanning 40 tabs before the morning meeting." in english.text
        spanish = client.get("/home?lang=es")
        assert '<html lang="es"' in spanish.text
        assert "Dejá de revisar 40 pestañas antes de la reunión de pauta." in spanish.text
        assert client.cookies["radar_lang"] == "es"
        assert 'lang="es"' in client.get("/login").text
        assert 'lang="es"' in client.get("/home?lang=xx").text
        assert 'lang="en"' in client.get("/login?lang=en").text
        assert "Sign in to Agenda Radar" in client.get("/login").text
