"""Tests covering Phase 1-4 improvements: connectors, clustering, AI, agents, UX & caching."""

import asyncio
import gzip
import io
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from sqlalchemy import func, select

from agenda_radar.agents import run_agent
from agenda_radar.ai import generate
from agenda_radar.alerts import deliver_notifications
from agenda_radar.assistant import has_unsupported_numbers, profile_answer
from agenda_radar.collaboration_models import AgentRun, AIProfile, ChannelDelivery, EditorialAgent
from agenda_radar.editorial import active_config, publish_config
from agenda_radar.ingest import classify_topic, poll_source, store_document
from agenda_radar.maintenance import maintain
from agenda_radar.models import (
    Alert,
    Event,
    IngestRun,
    Job,
    Mention,
    Notification,
    Source,
    State,
    TelegramLink,
    TrendSample,
)
from agenda_radar.network import MAX_BYTES, FetchError, _read_bounded
from agenda_radar.schemas import Answer, DocumentInput
from agenda_radar.scoring import compare
from agenda_radar.telegram_bot import Telegram


def test_telegram_delivery_handles_none_metrics(app):
    db = app.state.db
    with db.session() as session:
        _, config = active_config(session)
        config.telegram_enabled = True
        config.quiet_start = config.quiet_end = 0
        publish_config(session, config, 1, "Enable TG")
        ev = Event(label="Evento sin cobertura propia")
        session.add(ev)
        session.flush()
        alert = Alert(
            event_id=ev.id,
            rule="priority_without_coverage",
            dedupe_key="test:none-metrics",
            payload={
                "label": ev.label,
                "reference_share": 42.5,
                "own_share": None,
                "gap_pp": None,
                "independent_source_count": 3,
                "documents": [{"id": 1, "url": "https://medio.test/1"}],
            },
        )
        session.add(alert)
        session.flush()
        session.add(TelegramLink(user_id=1, chat_id=999))
        session.add(Notification(alert_id=alert.id, user_id=1, expires_at=time.time() + 3600))
    sent = []

    class FakeTG:
        async def call(self, method, payload):
            sent.append((method, payload))
            return {}

    asyncio.run(deliver_notifications(db, FakeTG(), app.state.settings))
    assert len(sent) == 1
    assert "sin datos" in sent[0][1]["text"]
    with db.session() as session:
        assert session.scalar(select(Notification)).status == "sent"


def test_telegram_callback_acknowledges_query(app):
    db = app.state.db
    with db.session() as session:
        ev = Event(label="Evento callback")
        session.add(ev)
        session.flush()
        ev_id = ev.id
        session.add(TelegramLink(user_id=2, chat_id=777))
    calls = []
    bot = Telegram(db, app.state.vault)

    async def fake_call(method, payload):
        calls.append((method, payload))
        return {}

    bot.call = fake_call
    asyncio.run(
        bot.handle(
            {
                "update_id": 55,
                "callback_query": {
                    "id": "cb-123",
                    "data": f"follow:{ev_id}",
                    "message": {"chat": {"id": 777, "type": "private"}},
                },
            }
        )
    )
    methods = [m for m, _ in calls]
    assert "answerCallbackQuery" in methods
    assert "sendMessage" in methods


def test_bounded_gzip_decompression_and_zip_bomb_protection():
    payload = b"<rss><channel><item><title>OK</title></item></channel></rss>"
    compressed = gzip.compress(payload)
    assert _read_bounded(io.BytesIO(compressed), "gzip") == payload

    bomb = gzip.compress(b"A" * (MAX_BYTES + 4096))
    with pytest.raises(FetchError, match="response_too_large"):
        _read_bounded(io.BytesIO(bomb), "gzip")


def test_x_poll_persists_since_id(app, monkeypatch):
    db = app.state.db
    with db.session() as session:
        src = Source(
            name="Cuenta X",
            kind="x",
            channel="x",
            scope="public",
            url="https://x.com/example",
            group_name="Cuenta X",
            legal_basis="API oficial",
            options={"user_id": "12345"},
        )
        session.add(src)
        session.flush()
        src_id = src.id
        app.state.vault.set(session, "x", "fake-token")
    monkeypatch.setattr(
        "agenda_radar.x_connector.poll_x",
        lambda source, token: [
            DocumentInput(url="https://x.com/i/status/100", title="Post 1", external_id="100"),
            DocumentInput(url="https://x.com/i/status/250", title="Post 2", external_id="250"),
        ],
    )
    poll_source(db, src_id, app.state.vault)
    with db.session() as session:
        assert session.get(Source, src_id).options["since_id"] == "250"


def test_hybrid_clustering_groups_paraphrased_news_and_separates_unrelated(app):
    db = app.state.db
    with db.session() as session:
        s1 = Source(name="Diario Uno", url="https://uno.test/rss", group_name="Uno", legal_basis="RSS público", status="healthy", last_success=time.time())
        s2 = Source(name="Diario Dos", url="https://dos.test/rss", group_name="Dos", legal_basis="RSS público", status="healthy", last_success=time.time())
        session.add_all([s1, s2])
        session.flush()
        d1 = store_document(
            session,
            s1,
            DocumentInput(
                url="https://uno.test/bcra-tasa",
                title="El BCRA bajó la tasa de interés tras el dato de inflación del INDEC",
                excerpt="El Banco Central recortó la tasa monetaria luego de difundirse el índice mensual del INDEC.",
            ),
        )
        d2 = store_document(
            session,
            s2,
            DocumentInput(
                url="https://dos.test/tasa-bcra",
                title="Banco Central recorta tasas de referencia luego del índice de inflación",
                excerpt="La autoridad monetaria BCRA ajustó las tasas tras el informe del INDEC sobre precios.",
            ),
        )
        d3 = store_document(
            session,
            s2,
            DocumentInput(
                url="https://dos.test/futbol",
                title="Selección argentina convoca juveniles para amistosos de verano",
                excerpt="El entrenador confirmó la lista de jugadores citados para la gira.",
            ),
        )
        e1 = session.get(Mention, d1.id).event_id
        e2 = session.get(Mention, d2.id).event_id
        e3 = session.get(Mention, d3.id).event_id
        assert e1 == e2
        assert e3 != e1


def test_topic_classification_uses_best_keyword_score():
    keywords = {
        "política": ["gobierno", "congreso"],
        "economía": ["inflación", "dólar", "presupuesto"],
    }
    assert (
        classify_topic("El gobierno presentó datos de inflación, dólar y presupuesto", keywords)
        == "economía"
    )


def test_starter_packs_api_and_idempotency(client):
    packs = client.get("/api/v1/admin/sources/packs")
    assert packs.status_code == 200
    assert any(p["id"] == "ar_national" for p in packs.json())
    first = client.post("/api/v1/admin/sources/packs/ar_national/apply", json={})
    assert first.status_code == 200
    assert first.json()["created"] >= 5
    second = client.post("/api/v1/admin/sources/packs/ar_national/apply", json={})
    assert second.status_code == 200
    assert second.json()["created"] == 0
    assert second.json()["skipped"] == first.json()["created"]


def test_numeric_guard_allows_meta_counts_but_blocks_invented_facts():
    evidence = [{"id": 12, "title": "Puente reabierto", "excerpt": "Reabrió hoy.", "url": "https://a.test/1"}]
    assert not has_unsupported_numbers("Hay 1 publicación en las últimas 24 horas (doc 12).", evidence, "24h")
    assert has_unsupported_numbers("Hubo 947 afectados según el informe.", evidence, "24h")


def test_unified_profile_answer_uses_tone_and_prompt(app, monkeypatch):
    profile = AIProfile(id=1, enabled=True, network="internal")
    evidence = [{"id": 1, "title": "Nota", "excerpt": "Texto", "url": "https://a.test/1"}]
    captured = []

    def fake_gen(db, vault, pid, op, instructions, context, schema):
        captured.append(instructions)
        return Answer(answer="Resumen", citation_document_ids=[1], confidence="high", limitations=[], suggested_action=None), 1

    monkeypatch.setattr("agenda_radar.ai.generate", fake_gen)
    res = profile_answer(
        app.state.db, app.state.vault, profile, "Resumen", evidence, "es",
        purpose="daily_brief", prompt_template="Priorizar impacto local.", editorial_tone="Sobrio."
    )
    assert res["mode"] == "ai"
    assert "Priorizar impacto local." in captured[0]
    assert "Sobrio." in captured[0]


def test_compatible_local_model_falls_back_from_strict_json_schema(app, monkeypatch):
    from agenda_radar.collaboration_worker import ConnectionProbe

    attempts = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            fmt = body["response_format"]["type"]
            attempts.append(fmt)
            if fmt == "json_schema":
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error":"json_schema unsupported"}')
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"choices":[{"message":{"content":"{\\"message\\":\\"OK\\"}"}}]}')

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("AI_INTERNAL_HOSTS", "127.0.0.1")
    try:
        with app.state.db.session() as session:
            profile = AIProfile(
                name="Ollama", provider="compatible", network="internal", model="llama3",
                enabled=True, base_url=f"http://127.0.0.1:{server.server_port}/v1"
            )
            session.add(profile)
            session.flush()
            pid = profile.id
        res, _ = generate(app.state.db, app.state.vault, pid, "test", "Return OK", {}, ConnectionProbe)
        assert res.message == "OK"
        assert attempts == ["json_schema", "json_object"]
    finally:
        server.shutdown()
        server.server_close()


def test_multichannel_web_agent_works_without_slack(client, app):
    with app.state.db.session() as session:
        src = Source(name="Local", url="https://local.test/rss", group_name="Local", legal_basis="RSS", status="healthy", last_success=time.time())
        session.add(src)
        session.flush()
        store_document(session, src, DocumentInput(url="https://local.test/1", title="Obra vial en el centro"))
    created = client.post(
        "/api/v1/admin/agents",
        json={"name": "Web Brief", "kind": "briefing", "channel_id": "web", "enabled": True},
    )
    assert created.status_code == 200, created.text
    agent_id = created.json()["id"]
    result = run_agent(app.state.db, app.state.vault, agent_id, preview=False)
    assert len(result["items"]) == 1
    with app.state.db.session() as session:
        delivery = session.scalar(select(ChannelDelivery))
        assert delivery is not None and delivery.channel == "web" and delivery.status == "sent"


def test_maintenance_prunes_operational_tables_and_orphan_events(app):
    db = app.state.db
    old = time.time() - 100 * 86400
    with db.session() as session:
        src = Source(name="Old", url="https://old.test/rss", group_name="Old", legal_basis="RSS")
        session.add(src)
        session.flush()
        session.add(IngestRun(source_id=src.id, started_at=old, status="done"))
        session.add(Job(kind="poll", payload={}, status="done", run_after=old, idempotency_key="old-job"))
        session.add(State(key="telegram_handled:1", value={"at": old}))
        session.add(Event(label="Orphan event", first_observed_at=old))
        agent = EditorialAgent(name="A", kind="briefing")
        session.add(agent)
        session.flush()
        session.add(AgentRun(agent_id=agent.id, at=old, result={}))
    report = maintain(db)
    assert report["events_removed"] >= 1
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 0
        assert session.scalar(select(func.count()).select_from(IngestRun)) == 0
        assert session.scalar(select(func.count()).select_from(AgentRun)) == 0
        assert session.get(State, "telegram_handled:1") is None


def test_compare_cache_invalidates_on_new_document_and_1h_velocity(app):
    db = app.state.db
    with db.session() as session:
        s1 = Source(name="A", url="https://a.test/rss", group_name="A", legal_basis="RSS", status="healthy", last_success=time.time())
        s2 = Source(name="B", url="https://b.test/rss", group_name="B", legal_basis="RSS", status="healthy", last_success=time.time())
        session.add_all([s1, s2])
        session.flush()
        store_document(session, s1, DocumentInput(url="https://a.test/1", title="Suba de tarifas eléctricas", published_at=time.time() - 2400))
        first = compare(session, "1h")
        assert first["rows"][0]["velocity_method"] == "30m_vs_previous_30m_unadjusted"
        store_document(session, s2, DocumentInput(url="https://b.test/2", title="Nuevo parque urbano inaugurado", published_at=time.time() - 60))
        second = compare(session, "1h")
        assert len(second["rows"]) == 2


def test_event_page_cross_references_trends(client, app):
    with app.state.db.session() as session:
        s1 = Source(name="Diario", url="https://diario.test/rss", group_name="Diario", legal_basis="RSS", status="healthy", last_success=time.time())
        s_tr = Source(name="Trends", kind="google_trends", channel="search", scope="public", url="https://trends.google.com/trending/rss?geo=AR", group_name="Trends", legal_basis="RSS")
        session.add_all([s1, s_tr])
        session.flush()
        doc = store_document(session, s1, DocumentInput(url="https://diario.test/dolar", title="Dólar oficial cierra en alza"))
        ev_id = session.get(Mention, doc.id).event_id
        session.add(TrendSample(source_id=s_tr.id, label="Dólar oficial hoy", source_url="https://trends.google.com/1"))
    page = client.get(f"/events/{ev_id}")
    assert page.status_code == 200
    assert "Dólar oficial hoy" in page.text
