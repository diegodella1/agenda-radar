import json
import time

from demo_helpers import prepare_corpus
from fastapi.testclient import TestClient
from sqlalchemy import select

from agenda_radar.app import create_app
from agenda_radar.config import Settings
from agenda_radar.db import Database
from agenda_radar.demo_corpus import collect_once, read_snapshot, sync_catalog
from agenda_radar.models import Source
from agenda_radar.network import FetchError, public_addresses


def test_catalog_idempotent_groups_and_channels(tmp_path):
    db = Database(tmp_path / "catalog.db")
    db.migrate()
    with db.session() as session:
        sync_catalog(session)
    with db.session() as session:
        sync_catalog(session)
    with db.session() as session:
        sources = list(session.scalars(select(Source)))
        assert all(s.poll_interval == 3600 for s in sources)
        assert len(sources) < 30
        assert len({s.options["catalog_id"] for s in sources}) == len(sources)
        assert {s.group_name for s in sources if s.name in ("La Voz", "Los Andes")} == {"Grupo Clarín"}
        assert all(s.scope == "public" for s in sources if s.channel in ("x", "video", "search"))
        assert all(s.kind == "rss" for s in sources if s.channel == "video")
        assert all(s.options["profile_evidence"].startswith("https://")
                   for s in sources if s.options.get("profiles"))
    db.engine.dispose()


def test_failed_collection_preserves_last_good_snapshot(tmp_path, monkeypatch):
    original = prepare_corpus(tmp_path)

    def unavailable(*args, **kwargs):
        raise FetchError("http_429")

    monkeypatch.setattr("agenda_radar.demo_corpus.poll_source", unavailable)
    result = collect_once(tmp_path, force=True)
    assert not result["ready"]
    assert read_snapshot(tmp_path) == original
    assert not json.loads((tmp_path / "public/status.json").read_text())["ready"]
    assert not list((tmp_path / "public").glob(".snapshot-*"))


def test_empty_demo_prepares_without_synthetic_news(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "prod", demo_dir=tmp_path / "visits",
                              demo_corpus_dir=tmp_path / "absent", demo_enabled=True,
                              default_language="es",
                              cookie_secure=False, app_base_url="http://testserver"))
    with TestClient(app) as client:
        client.headers["X-Requested-With"] = "AgendaRadar"
        result = client.post("/demo/api/v1/auth/login", json={"email": "demo", "password": "demo"})
        deadline = time.monotonic() + 60
        while result.status_code == 202 and time.monotonic() < deadline:
            time.sleep(0.1)
            result = client.post("/demo/api/v1/auth/login", json={"email": "demo", "password": "demo"})
        assert result.status_code == 200
        client.headers["X-CSRF-Token"] = result.json()["csrf"]
        assert "Preparando primera captura" in client.get("/demo/").text
        assert not client.get("/demo/api/v1/agendas/compare").json()["rows"]
        assert client.post("/demo/api/v1/demo/news", json={}).json()["documents_added"] == 0
        prepare_corpus(tmp_path / "absent")
        assert client.post("/demo/api/v1/demo/news", json={}).json()["documents_added"] > 0
        assert client.get("/demo/api/v1/demo/status").json()["ready"]
        exported = client.get("/demo/api/v1/export/agenda.md").text
        assert "Cobertura propia simulada" in exported
        assert "demo.invalid" not in exported
    app.state.db.engine.dispose()


def test_ipv4_preference_does_not_skip_ssrf_validation(monkeypatch):
    import socket

    import pytest

    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [
        (socket.AF_INET6, 1, 6, "", ("2606:4700::6810:7019", 443, 0, 0)),
        (socket.AF_INET, 1, 6, "", ("104.16.112.25", 443))])
    assert public_addresses("https://example.com")[2][0] == "104.16.112.25"
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [
        (socket.AF_INET, 1, 6, "", ("104.16.112.25", 443)),
        (socket.AF_INET6, 1, 6, "", ("::1", 443, 0, 0))])
    with pytest.raises(FetchError, match="ssrf_blocked"):
        public_addresses("https://example.com")
