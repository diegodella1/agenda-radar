import asyncio

from sqlalchemy import func, select

from agenda_radar.assistant import answer_query
from agenda_radar.ingest import poll_source
from agenda_radar.jobs import claim, enqueue, finish
from agenda_radar.models import Document, Source, TelegramLink
from agenda_radar.network import FetchResult
from agenda_radar.security import pairing_code
from agenda_radar.telegram_bot import Telegram


def test_real_pipeline_with_injected_transport(app, monkeypatch):
    feed = b"<rss><channel><item><guid>1</guid><title>Congreso aprueba presupuesto educativo</title><link>https://medio.test/1</link></item></channel></rss>"
    monkeypatch.setattr(
        "agenda_radar.ingest.fetch",
        lambda *a, **kw: FetchResult("https://medio.test/rss", 200, feed, {}),
    )
    with app.state.db.session() as session:
        source = Source(
            name="Medio",
            url="https://medio.test/rss",
            group_name="Medio",
            legal_basis="Fixture",
            kind="rss",
        )
        session.add(source)
        session.flush()
        identifier = source.id
    db = app.state.db
    job_id = enqueue(db, "poll", {"source_id": identifier}, "test-pipeline")
    job = claim(db, "test-worker")
    assert job is not None and job.id == job_id
    result = poll_source(db, identifier)
    finish(db, job_id, "test-worker", result)
    poll_source(db, identifier)
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(Document)) == 1
        assert session.get(Source, identifier).status == "healthy"


def test_telegram_pair_unknown_chat_and_disabled_user(app):
    calls = []
    bot = Telegram(app.state.db, app.state.vault)

    async def fake_call(method, payload):
        calls.append((method, payload))
        return {}

    bot.call = fake_call
    asyncio.run(
        bot.handle(
            {"update_id": 1, "message": {"chat": {"id": 42, "type": "private"}, "text": "/agenda"}}
        )
    )
    assert calls == []
    with app.state.db.session() as session:
        code = pairing_code(session, 2)
    asyncio.run(
        bot.handle(
            {
                "update_id": 2,
                "message": {"chat": {"id": 42, "type": "private"}, "text": "/start " + code},
            }
        )
    )
    assert "vinculado" in calls[-1][1]["text"]
    with app.state.db.session() as session:
        assert session.get(TelegramLink, 2).code_hash is None
    asyncio.run(
        bot.handle(
            {"update_id": 3, "message": {"chat": {"id": 42, "type": "private"}, "text": "/agenda"}}
        )
    )
    assert "Sin datos" in calls[-1][1]["text"]


def test_query_outside_corpus_and_no_ai(app):
    answer = answer_query(app.state.db, app.state.vault, "Tema ausente")
    assert answer["citation_document_ids"] == []
    assert answer["mode"] == "deterministic"


def test_preview_required_and_rollback(client):
    current = client.get("/api/v1/admin/config").json()
    payload = {"config": dict(current["config"]), "reason": "Ajuste editorial"}
    payload["config"]["topic_priorities"] = {"economía": 1.5}
    assert client.post("/api/v1/admin/config/publish", json=payload).status_code == 409
    assert client.post("/api/v1/admin/config/preview", json=payload).status_code == 200
    response = client.post("/api/v1/admin/config/publish", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["version"] > current["version"]
    assert (
        client.post(f"/api/v1/admin/config/{current['version']}/rollback", json={}).status_code
        == 200
    )
    assert client.get("/api/v1/admin/config").json()["config"] == current["config"]


def test_openai_invalid_citations_fall_back_without_inventing_links(app, monkeypatch):
    from types import SimpleNamespace

    from agenda_radar.editorial import active_config, publish_config
    from agenda_radar.ingest import store_document
    from agenda_radar.schemas import Answer, DocumentInput

    with app.state.db.session() as session:
        source = Source(
            name="Test", url="https://medio.test/rss", group_name="Test", legal_basis="Fixture", options={"data_policy": "external"}
        )
        session.add(source)
        session.flush()
        store_document(
            session,
            source,
            DocumentInput(url="https://medio.test/nota", title="Presupuesto educativo aprobado"),
        )
        _, config = active_config(session)
        config.ai_enabled = True
        config.ai_model = "test-model"
        config.ai_input_usd_million = 1
        config.ai_output_usd_million = 1
        publish_config(session, config, 1, "Prueba aislada")
        app.state.vault.set(session, "openai", "dummy-test-key")
    response = SimpleNamespace(
        output_parsed=Answer(
            answer="Texto con cita inválida",
            citation_document_ids=[999999],
            confidence="high",
            limitations=[],
            suggested_action=None,
        ),
        usage=SimpleNamespace(input_tokens=100, output_tokens=50),
    )
    monkeypatch.setattr(
        "openai.OpenAI",
        lambda **kwargs: SimpleNamespace(
            responses=SimpleNamespace(parse=lambda **kwargs: response)
        ),
    )
    answer = answer_query(app.state.db, app.state.vault, "Presupuesto educativo")
    assert answer["mode"] == "deterministic"
    assert 999999 not in answer["citation_document_ids"]
    assert all(item["url"] == "https://medio.test/nota" for item in answer["evidence"])


def test_extraction_keeps_only_literal_evidence_and_does_not_merge(app, monkeypatch):
    from types import SimpleNamespace

    from agenda_radar.editorial import active_config, publish_config
    from agenda_radar.enrichment import ExtractedEntity, Extraction, enrich_document
    from agenda_radar.ingest import store_document
    from agenda_radar.models import Mention
    from agenda_radar.schemas import DocumentInput

    with app.state.db.session() as session:
        source = Source(
            name="Test", url="https://medio.test/rss", group_name="Test", legal_basis="Fixture", options={"data_policy": "external"}
        )
        session.add(source)
        session.flush()
        document = store_document(
            session,
            source,
            DocumentInput(
                url="https://medio.test/nota", title="Congreso aprueba presupuesto educativo"
            ),
        )
        identifier, content_hash = document.id, document.content_hash
        session.flush()
        event_id = session.get(Mention, identifier).event_id
        _, config = active_config(session)
        config.ai_enabled = config.extraction_enabled = True
        config.ai_model = config.extraction_model = "test-model"
        config.extraction_input_usd_million = config.extraction_output_usd_million = 1
        publish_config(session, config, 1, "Prueba aislada")
        app.state.vault.set(session, "openai", "dummy-test-key")
    result = Extraction(
        document_id=identifier,
        topic="economía",
        entities=[
            ExtractedEntity(name="Congreso", evidence_span="Congreso aprueba"),
            ExtractedEntity(name="Entidad inventada", evidence_span="Texto inexistente"),
        ],
        related_document_id=999999,
        reason="Relación inválida",
        confidence=0.99,
    )
    response = SimpleNamespace(
        output_parsed=result, usage=SimpleNamespace(input_tokens=100, output_tokens=50)
    )
    monkeypatch.setattr(
        "openai.OpenAI",
        lambda **kwargs: SimpleNamespace(
            responses=SimpleNamespace(parse=lambda **kwargs: response)
        ),
    )
    assert (
        enrich_document(app.state.db, app.state.vault, identifier, content_hash)["status"]
        == "enriched"
    )
    with app.state.db.session() as session:
        assert session.get(Document, identifier).entities == [
            {"name": "Congreso", "evidence_span": "Congreso aprueba"}
        ]
        assert session.get(Mention, identifier).event_id == event_id
