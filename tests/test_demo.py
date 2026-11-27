import time

import pytest
from demo_helpers import prepare_corpus, publish_news
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update

from agenda_radar.app import create_app
from agenda_radar.config import Settings
from agenda_radar.editorial import initialize_config
from agenda_radar.models import Document, Secret, Source, State, User
from agenda_radar.security import create_user, hash_password


@pytest.fixture
def demo_app(tmp_path):
    app = create_app(
        Settings(
            data_dir=tmp_path / "production",
            secrets_dir=tmp_path / "keys",
            demo_dir=tmp_path / "demo",
            demo_corpus_dir=tmp_path / "corpus",
            demo_enabled=True,
            default_language="es",
            cookie_secure=False,
            app_base_url="http://testserver",
            backup_dir=tmp_path / "backups",
        )
    )
    app.state.fixture_payload = prepare_corpus(tmp_path / "corpus")
    app.state.db.migrate()
    app.state.vault.initialize()
    with app.state.db.session() as session:
        initialize_config(session)
        create_user(session, "real@example.test", "real-password-long")
        app.state.vault.set(session, "openai", "private-production-key")
    yield app
    app.state.db.engine.dispose()


def login(client):
    client.headers["X-Requested-With"] = "AgendaRadar"
    response = client.post("/demo/api/v1/auth/login", json={"email": "demo", "password": "demo"})
    deadline = time.monotonic() + 60
    while response.status_code == 202 and time.monotonic() < deadline:
        time.sleep(0.1)
        response = client.post("/demo/api/v1/auth/login", json={"email": "demo", "password": "demo"})
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf"]
    return response


def test_demo_isolation_and_production_session(demo_app):
    with TestClient(demo_app) as first:
        first.headers["X-Requested-With"] = "AgendaRadar"
        real = first.post(
            "/api/v1/auth/login",
            json={"email": "real@example.test", "password": "real-password-long"},
        )
        assert real.status_code == 200
        login(first)
        second = TestClient(demo_app)
        second.portal = first.portal
        login(second)
        for client in (first, second):
            assert client.get("/demo/").status_code == 200
            assert len(client.get("/demo/api/v1/agendas/compare?window=7d").json()["rows"]) == 18
        decision = {"event_id": 1, "action": "follow", "reason": "private-first-visitor"}
        assert first.post("/demo/api/v1/editorial/decisions", json=decision).status_code == 200
        assert "private-first-visitor" in first.get("/demo/history").text
        assert "private-first-visitor" not in second.get("/demo/history").text
        assert first.get("/api/v1/auth/me").json()["email"] == "real@example.test"
        assert "real@example.test" not in first.get("/demo/").text
        assert second.get("/api/v1/events").status_code == 401
        with demo_app.state.db.session() as session:
            assert session.scalar(select(func.count()).select_from(Document)) == 0
            assert session.scalar(select(func.count()).select_from(User)) == 1
            assert session.scalar(select(func.count()).select_from(Secret)) == 1
        second.close()


def test_slow_demo_preparation_returns_json_without_blocking(demo_app, monkeypatch):
    import threading

    manager = demo_app.state.demo_manager
    original = manager.build_visit
    release = threading.Event()

    def slow_build(key):
        assert release.wait(30)
        return original(key)

    monkeypatch.setattr(manager, "build_visit", slow_build)
    with TestClient(demo_app) as client:
        client.headers["X-Requested-With"] = "AgendaRadar"
        try:
            for _ in range(22):
                response = client.post("/demo/api/v1/auth/login", json={"email": "demo", "password": "demo"})
                assert response.status_code == 202
                assert response.json()["pending"]
            assert len(manager.pending) == 1
            assert len(manager.login_attempts) == 1
            assert client.get("/health/live").status_code == 200
        finally:
            release.set()
        login(client)
        assert client.get("/demo/api/v1/auth/me").json()["email"] == "demo"


def test_failed_demo_preparation_returns_retryable_json(demo_app, monkeypatch):
    def fail(key):
        raise RuntimeError("fixture preparation failure")

    monkeypatch.setattr(demo_app.state.demo_manager, "build_visit", fail)
    with TestClient(demo_app) as client:
        client.headers["X-Requested-With"] = "AgendaRadar"
        response = client.post("/demo/api/v1/auth/login", json={"email": "demo", "password": "demo"})
        deadline = time.monotonic() + 10
        while response.status_code == 202 and time.monotonic() < deadline:
            time.sleep(0.1)
            response = client.post("/demo/api/v1/auth/login", json={"email": "demo", "password": "demo"})
        assert response.status_code == 503
        assert "Volvé a intentar" in response.json()["detail"]
        assert not demo_app.state.demo_manager.pending


def test_demo_scenario_news_reset_and_windows(demo_app):
    with TestClient(demo_app) as client:
        login(client)
        for window in ("1h", "6h", "24h", "72h", "7d"):
            result = client.get("/demo/api/v1/agendas/compare", params={"window": window}).json()
            assert result["rows"] and result["source_health"]["own"] == "healthy"
        coverage = client.post(
            "/demo/api/v1/editorial/coverage",
            json={
                "event_id": 1,
                "url": "https://demo.example/coverage",
                "published_at": time.time(),
            },
        )
        assert coverage.status_code == 200
        before = client.get("/demo/api/v1/agendas/compare").json()
        assert next(r for r in before["rows"] if r["event_id"] == 1)["own_covered"]
        first_doc = before["rows"][0]["documents"][0]
        assert first_doc["url"].startswith("https://")
        assert len(client.get("/demo/api/v1/alerts").json()) == 0
        publish_news(demo_app.state.demo_manager.settings.demo_corpus_dir, demo_app.state.fixture_payload)
        result = client.post("/demo/api/v1/demo/news", json={}).json()
        assert result["documents_added"] == 1
        assert client.post("/demo/api/v1/demo/news", json={}).json()["already_applied"]
        after = client.get("/demo/api/v1/agendas/compare").json()
        assert [r["reference_share"] for r in before["rows"]] != [
            r["reference_share"] for r in after["rows"]
        ]
        assert client.post("/demo/api/v1/demo/reset", json={}).status_code == 200
        assert not client.get("/demo/api/v1/demo/status").json()["news_applied"]
        assert len(client.get("/demo/api/v1/alerts").json()) == 0
        assert client.get("/demo/api/v1/auth/me").status_code == 200
        assert client.post("/demo/api/v1/demo/news", json={}).json()["documents_added"] == 0


def test_demo_blocks_privileged_and_external_work(demo_app, monkeypatch):
    import socket

    from agenda_radar.security import Vault

    def forbidden(*args, **kwargs):
        raise AssertionError("Demo must not access a network or secrets")

    with TestClient(demo_app) as client:
        login(client)
        monkeypatch.setattr(socket, "create_connection", forbidden)
        monkeypatch.setattr(socket, "getaddrinfo", forbidden)
        monkeypatch.setattr(Vault, "get", forbidden)
        for path in (
            "admin/providers",
            "admin/users",
            "admin/prompts",
            "admin/backups",
            "admin/jobs/1/retry",
            "telegram/pair",
            "auth/password",
            "auth/setup",
            "admin/sources/import",
            "admin/sources/1/documents",
        ):
            assert client.post("/demo/api/v1/" + path, json={}).status_code == 403
        for path in (
            "/account",
            "/setup",
            "/admin/users",
            "/admin/providers",
            "/admin/operations",
            "/api/v1/admin/backups/agenda-123.db",
            "/api/v1/admin/audit",
        ):
            assert client.get("/demo" + path).status_code == 403
        job = client.post("/demo/api/v1/assistant/query", json={"query": "transporte"}).json()
        answer = client.get(f"/demo/api/v1/jobs/{job['job_id']}").json()["result"]
        assert answer["mode"] == "deterministic" and answer["evidence"]
        source = client.get("/demo/api/v1/admin/sources").json()[0]
        payload = {k: source[k] for k in ("name", "url", "group_name", "legal_basis")}
        job = client.post("/demo/api/v1/admin/sources/test", json=payload).json()
        assert (
            client.get(f"/demo/api/v1/jobs/{job['job_id']}").json()["result"]["mode"] == "simulated"
        )
        assert client.post("/demo/api/v1/admin/sources/1/poll", json={}).status_code == 200
        config = client.get("/demo/api/v1/admin/config").json()["config"]
        config["ai_enabled"] = True
        assert (
            client.post(
                "/demo/api/v1/admin/config/preview", json={"config": config, "reason": "test"}
            ).status_code
            == 403
        )


def test_demo_csrf_cookies_expiry_capacity_and_cleanup(demo_app):
    demo_app.state.demo_manager.settings.demo_max_sessions = 1
    with TestClient(demo_app) as client:
        login(client)
        for cookie in client.cookies.jar:
            if cookie.name.startswith("radar_demo"):
                assert cookie.path == "/demo" and cookie.has_nonstandard_attr("HttpOnly")
        other = TestClient(demo_app)
        other.portal = client.portal
        other.headers["X-Requested-With"] = "AgendaRadar"
        response = other.post("/demo/api/v1/auth/login", json={"email": "demo", "password": "demo"})
        assert response.status_code == 503
        assert (
            client.post(
                "/demo/api/v1/demo/reset", json={}, headers={"X-CSRF-Token": "wrong"}
            ).status_code
            == 403
        )
        visit = next(iter(demo_app.state.demo_manager.visits.values()))
        directory = visit.directory
        visit.expires = time.time() - 1
        assert client.get("/demo/api/v1/demo/status").status_code == 401
        assert not directory.exists()
        login(other)
        assert other.post("/demo/api/v1/auth/logout", json={}).status_code == 200
        assert not demo_app.state.demo_manager.visits
        other.close()
    with pytest.raises(ValueError):
        hash_password("demo")


def test_demo_templates_and_criteria(demo_app):
    with TestClient(demo_app) as client:
        assert "/demo/static/app.js?v=" in client.get("/demo/login").text
        assert client.get("/demo/").url.path == "/demo/login"
        login(client)
        for path in (
            "/",
            "/compare",
            "/events",
            "/events/1",
            "/trends",
            "/alerts",
            "/history",
            "/assistant",
            "/integrations",
            "/admin/sources",
            "/admin/config",
        ):
            page = client.get("/demo" + path)
            assert page.status_code == 200, page.text
            assert 'href="/admin/' not in page.text
            assert "Demo interactiva" in page.text
        config = client.get("/demo/api/v1/admin/config").json()["config"]
        config["minimum_gap_pp"] = 8
        payload = {"config": config, "reason": "Probar una brecha distinta"}
        assert client.post("/demo/api/v1/admin/config/preview", json=payload).status_code == 200
        assert client.post("/demo/api/v1/admin/config/publish", json=payload).status_code == 200
        assert client.get("/demo/api/v1/admin/config").json()["config"]["minimum_gap_pp"] == 8
        assert client.get("/demo/api/v1/export/agenda.md").status_code == 200


def test_visual_view_filters_evidence_and_momentum(demo_app):
    with TestClient(demo_app) as client:
        login(client)
        complete = client.get("/demo/api/v1/agendas/compare?window=7d").json()
        row = complete["rows"][0]
        filtered = client.get(
            "/demo/api/v1/agendas/compare",
            params={"window": "7d", "topic": row["topic"], "source": row["source_ids"][0]},
        ).json()
        assert filtered["denominator_scope"] == "original_universe"
        assert filtered["universe_count"] == len(complete["rows"])
        match = next(r for r in filtered["rows"] if r["event_id"] == row["event_id"])
        for key in ("reference_share", "own_share", "gap_pp", "priority", "components"):
            assert match[key] == row[key]
        assert "window=7d" in match["href"] and "topic=" in match["href"]
        assert all(d["source_ids"] for d in match["documents"])
        for topic in filtered["topic_summary"]:
            assert topic["reference_share"] == pytest.approx(
                sum(r["reference_share"] for r in filtered["rows"] if r["topic"] == topic["label"])
            )
        assert match["confidence_pct"] == round(match["confidence"] * 100)
        page = client.get("/demo" + match["href"])
        assert page.status_code == 200 and "Ventana 7d" in page.text
        assert "probabilidad de veracidad" in page.text
        empty = client.get("/demo/api/v1/agendas/compare?topic=missing").json()
        assert empty["rows"] == [] and empty["topic_summary"] == []
        assert "Sin acontecimientos" in client.get("/demo/?topic=missing").text
        publish_news(demo_app.state.demo_manager.settings.demo_corpus_dir, demo_app.state.fixture_payload)
        changes = client.post("/demo/api/v1/demo/news", json={}).json()["affected_events"]
        assert len(changes) == 1 and all(c["after"] is not None for c in changes)
        assert changes[0]["before"] == changes[0]["after"]  # Same publisher is not extra independence.


def test_visual_missing_data_is_not_zero(client):
    result = client.get("/api/v1/agendas/compare").json()
    assert result["rows"] == []
    assert result["source_health"]["own"] == "insufficient"
    assert "Sin acontecimientos" in client.get("/").text


def test_onboarding_readiness_checks_current_visit_data(demo_app):
    with TestClient(demo_app) as client:
        login(client)
        page = client.get("/demo/").text
        for item in ("sources", "criteria", "news"):
            assert f'data-{item}-ready="true"' in page
        assert "/static/onboarding.js?v=" in page
        visit = next(iter(demo_app.state.demo_manager.visits.values()))
        with visit.app.state.db.session() as session:
            session.execute(update(Source).values(enabled=False))
            session.execute(delete(State).where(State.key == "active_config"))
            # A stale scenario flag alone must not claim the news is ready.
            session.execute(update(Document).values(title="[Cobertura simulada] Solo ejemplo"))
        page = client.get("/demo/").text
        for item in ("sources", "criteria", "news"):
            assert f'data-{item}-ready="false"' in page


def test_onboarding_preparing_without_corpus_and_absent_in_production(demo_app, tmp_path):
    demo_app.state.demo_manager.settings.demo_corpus_dir = tmp_path / "missing-corpus"
    with TestClient(demo_app) as client:
        login(client)
        page = client.get("/demo/").text
        assert 'data-sources-ready="true"' in page
        assert 'data-criteria-ready="true"' in page
        assert 'data-news-ready="false"' in page
        response = client.post("/api/v1/auth/login", json={
            "email": "real@example.test", "password": "real-password-long"})
        assert response.status_code == 200
        page = client.get("/").text
        assert 'id="demo-tour"' not in page
        assert 'id="editorial-help"' in page


def test_preloaded_login_does_not_seed_or_migrate(demo_app, monkeypatch):
    from agenda_radar.db import Database

    manager = demo_app.state.demo_manager
    manager.refresh_template()

    def forbidden(*args, **kwargs):
        raise AssertionError("Login must only copy the prepared database")

    monkeypatch.setattr("agenda_radar.demo.seed", forbidden)
    monkeypatch.setattr(Database, "migrate", forbidden)
    with TestClient(demo_app) as client:
        client.headers["X-Requested-With"] = "AgendaRadar"
        login(client)
        assert client.get("/demo/api/v1/auth/me").status_code == 200


def test_template_refresh_failure_and_restart(demo_app, monkeypatch):
    from agenda_radar.demo import DemoManager

    manager = demo_app.state.demo_manager
    manager.refresh_template()
    original = manager.template_path.read_bytes()
    updated = publish_news(manager.settings.demo_corpus_dir, demo_app.state.fixture_payload)
    build = manager.build_seed

    def fail(*args):
        raise RuntimeError("interrupted refresh")

    monkeypatch.setattr(manager, "build_seed", fail)
    with pytest.raises(RuntimeError):
        manager.refresh_template()
    assert manager.template_path.read_bytes() == original
    visit = manager.build_visit("a" * 64)
    with visit.app.state.db.session() as session:
        assert session.get(State, "demo_scenario").value["snapshot_id"] != updated["snapshot_id"]
    visit.app.state.db.engine.dispose()
    monkeypatch.setattr(manager, "build_seed", build)
    manager.refresh_template()
    restarted = DemoManager(manager.settings)
    monkeypatch.setattr(restarted, "build_seed", fail)
    restarted.refresh_template()
    visit = restarted.build_visit("b" * 64)
    with visit.app.state.db.session() as session:
        assert session.get(State, "demo_scenario").value["snapshot_id"] == updated["snapshot_id"]
    visit.app.state.db.engine.dispose()


def test_login_during_template_refresh_uses_previous(demo_app, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    manager = demo_app.state.demo_manager
    manager.refresh_template()
    publish_news(manager.settings.demo_corpus_dir, demo_app.state.fixture_payload)
    started, release = threading.Event(), threading.Event()
    build = manager.build_seed

    def slow_build(*args):
        started.set()
        assert release.wait(10)
        return build(*args)

    monkeypatch.setattr(manager, "build_seed", slow_build)
    with ThreadPoolExecutor() as executor:
        refresh = executor.submit(manager.refresh_template)
        try:
            assert started.wait(5)
            visit = manager.build_visit("c" * 64)
            with visit.app.state.db.session() as session:
                assert session.get(State, "demo_scenario").value["snapshot_id"] == demo_app.state.fixture_payload["snapshot_id"]
            visit.app.state.db.engine.dispose()
        finally:
            release.set()
        refresh.result()


def test_template_invalidates_code_and_retains_missing_corpus(demo_app):
    manager = demo_app.state.demo_manager
    manager.refresh_template()
    initial = manager.template_path.read_bytes()
    manager.settings.demo_corpus_dir.joinpath("public/latest.json").unlink()
    manager.refresh_template()
    assert manager.template_path.read_bytes() == initial
    prepare_corpus(manager.settings.demo_corpus_dir)
    manager.template_version = "new-preparation-version"
    manager.refresh_template()
    visit = manager.build_visit("d" * 64)
    with visit.app.state.db.session() as session:
        assert session.get(State, "demo_scenario").value["ready"]
    visit.app.state.db.engine.dispose()
    assert manager.template_path.read_bytes() != initial
