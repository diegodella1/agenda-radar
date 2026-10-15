import time

import pytest
from sqlalchemy import func, select

from agenda_radar.alerts import evaluate_alerts
from agenda_radar.assistant import reserve_budget
from agenda_radar.editorial import active_config, publish_config
from agenda_radar.events import split_event
from agenda_radar.ingest import canonical_url, parse_feed, store_document
from agenda_radar.models import Document, DocumentVersion, Event, Mention, Source
from agenda_radar.network import FetchError
from agenda_radar.schemas import DocumentInput
from agenda_radar.scoring import compare, snapshot


def source(session, name, scope="reference", group=None):
    obj = Source(
        name=name,
        url=f"https://{name}.test/rss",
        kind="rss",
        scope=scope,
        group_name=group or name,
        legal_basis="Test fixture",
        status="healthy",
        last_success=time.time(),
    )
    session.add(obj)
    session.flush()
    return obj


def document(name, title="Congreso aprueba presupuesto nacional para educación", path="nota"):
    return DocumentInput(
        url=f"https://{name}.test/{path}", title=title, published_at=time.time() - 60
    )


def test_dedupe_preserves_publishers_and_versions(app):
    with app.state.db.session() as session:
        a, b = source(session, "a"), source(session, "b")
        first = store_document(session, a, document("a"))
        store_document(session, a, document("a"))
        store_document(session, b, document("b"))
        assert session.scalar(select(func.count()).select_from(Document)) == 2
        assert session.scalar(select(func.count()).select_from(Event)) == 1
        item = document("a")
        item.excerpt = "Corrección del texto"
        store_document(session, a, item)
        assert session.scalar(select(func.count()).select_from(DocumentVersion)) == 1
        assert session.get(Mention, first.id)


def test_same_owner_counts_once(app):
    with app.state.db.session() as session:
        for name in ["a", "b", "c", "d"]:
            store_document(session, source(session, name, group="grupo-uno"), document(name))
        result = compare(session)
        assert result["rows"][0]["independent_source_count"] == 1
        assert result["rows"][0]["reference_share"] is None


def test_own_down_suppresses_gap_alert(app):
    with app.state.db.session() as session:
        for name in ["a", "b", "c"]:
            store_document(session, source(session, name), document(name))
        own = source(session, "own", "own")
        store_document(session, own, document("own", "Municipio inaugura nueva plaza barrial"))
        session.flush()
        result = compare(session)
        assert any(row["gap_pp"] is not None for row in result["rows"])
        assert evaluate_alerts(session, result) == 1
        session.flush()
        assert evaluate_alerts(session, result) == 0
        own.status = "degraded"
        session.flush()
        result = compare(session)
        assert all(row["gap_pp"] is None for row in result["rows"])
        assert evaluate_alerts(session, result) == 0


def test_weights_snapshot_and_empty_own(app):
    with app.state.db.session() as session:
        a, b = source(session, "a"), source(session, "b")
        store_document(session, a, document("a"))
        store_document(session, b, document("b", "Municipio inaugura nueva plaza barrial"))
        session.flush()
        original = snapshot(session)
        _, config = active_config(session)
        config.source_weights = {str(a.id): 10}
        changed = compare(session, config=config)
        assert changed["rows"][0]["reference_share"] != original["rows"][0]["reference_share"]
        assert all(row["own_share"] is None for row in changed["rows"])
        version = publish_config(session, config, 1, "Cambiar pesos")
        assert version > original["config_version"]


def test_split_persists_when_reingesting(app):
    with app.state.db.session() as session:
        a, b = source(session, "a"), source(session, "b")
        doca = store_document(session, a, document("a"))
        docb = store_document(session, b, document("b"))
        session.flush()
        old = session.get(Mention, doca.id).event_id
        new = split_event(session, old, [docb.id], "Otro hecho revisado", 1)
        session.flush()
        store_document(session, b, document("b"))
        assert session.get(Mention, docb.id).event_id == new


def test_xml_and_canonicalization():
    assert (
        canonical_url("https://Example.com/a?utm_source=foo&id=3#x") == "https://example.com/a?id=3"
    )
    body = b"<rss><channel><item><title>Hola</title><link>https://example.com/a</link></item></channel></rss>"
    assert parse_feed(body, "https://example.com/rss")[0].title == "Hola"
    for body in [b"<html></html>", b"<!DOCTYPE root><rss/>", b"not xml"]:
        with pytest.raises(FetchError):
            parse_feed(body, "https://example.com")


def test_budget_reservations_are_enforced(app):
    with app.state.db.session() as session:
        _, config = active_config(session)
    config.daily_budget_usd = 0.01
    reserve_budget(app.state.db, config, "answer", "configured-model", 0.009)
    with pytest.raises(ValueError, match="budget_exhausted"):
        reserve_budget(app.state.db, config, "answer", "configured-model", 0.009)


def test_admin_roundtrip_and_xss(client):
    payload = {
        "name": "<script>alert(1)</script>",
        "url": "https://example.com/feed",
        "group_name": "Example",
        "legal_basis": "Fixture autorizado",
    }
    response = client.post("/api/v1/admin/sources", json=payload)
    assert response.status_code == 200, response.text
    source_id = response.json()["id"]
    assert "<script>alert(1)</script>" not in client.get("/admin/sources").text
    response = client.post(
        f"/api/v1/admin/sources/{source_id}/documents",
        json={"title": "Prueba editorial", "url": "https://example.com/nota"},
    )
    assert response.status_code == 200, response.text
    assert client.get("/").status_code == 200
    assert client.get("/api/v1/export/agenda.md").status_code == 200
