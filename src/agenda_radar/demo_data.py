"""Public snapshots in isolated visits; only client coverage is simulated."""

import hashlib

from sqlalchemy import delete, select

from .demo_catalog import TOPIC_KEYWORDS, VERSION, catalog
from .editorial import initialize_config
from .ingest import store_document
from .models import (
    Base,
    ConfigVersion,
    Document,
    Event,
    Mention,
    Observation,
    Source,
    State,
    TrendSample,
)
from .schemas import DocumentInput


def import_snapshot(session, payload):
    sources = {s.options.get("catalog_id"): s for s in session.scalars(select(Source))}
    for row in payload["sources"]:
        key = row["options"]["catalog_id"]
        if key not in sources:
            source = Source(**{k: v for k, v in row.items() if k != "id"})
            session.add(source)
            sources[key] = source
        else:
            source = sources[key]
            for field in ("status", "error_code", "last_success"):
                setattr(source, field, row[field])
    session.flush()
    count = 0
    affected = set()
    for row in payload["documents"]:
        source = sources[row["source_key"]]
        item = DocumentInput(**row["item"])
        existing = session.scalar(select(Observation).where(
            Observation.source_id == source.id, Observation.external_id == item.external_id))
        document = store_document(session, source, item, now=row["observed_at"])
        document.ingested_at = row["ingested_at"]
        if existing is None:
            count += 1
            affected.add(session.get(Mention, document.id).event_id)
    for row in payload["trends"]:
        source = sources[row["source_key"]]
        existing = session.scalar(select(TrendSample.id).where(
            TrendSample.source_id == source.id, TrendSample.label == row["label"],
            TrendSample.captured_at == row["captured_at"]))
        if existing is None:
            session.add(TrendSample(source_id=source.id, **{k: v for k, v in row.items() if k != "source_key"}))
    session.flush()
    return count, affected


def simulate_coverage(session, now, base_url):
    own = Source(name="DEMO · Horizonte Federal", kind="manual", scope="own",
                 url=base_url, group_name="Cliente ficticio · Horizonte Federal", channel="web",
                 country="AR", status="healthy", last_success=now,
                 legal_basis="Cobertura propia simulada sobre acontecimientos reales",
                 options={"catalog_id": "horizonte-federal-demo", "simulated": True})
    session.add(own)
    session.flush()
    for event in session.scalars(select(Event).order_by(Event.id)):
        if int(hashlib.sha256(event.label.encode()).hexdigest()[:8], 16) % 3:
            continue
        doc = Document(publisher=own.name, group_name=own.group_name,
                       canonical_url=f"{base_url}/evidence/pending-{event.id}",
                       title="[Cobertura simulada] " + event.label,
                       excerpt="Ejercicio editorial de Horizonte Federal, cliente ficticio. "
                       "Esta cobertura no fue publicada. Consultá las referencias reales del acontecimiento.",
                       content_hash=hashlib.sha256(f"simulated:{event.id}".encode()).hexdigest(),
                       topic=event.topic, channel="web", published_at=event.first_observed_at,
                       observed_at=event.first_observed_at, ingested_at=now)
        session.add(doc)
        session.flush()
        doc.canonical_url = f"{base_url}/evidence/{doc.id}"
        session.add(Observation(source_id=own.id, document_id=doc.id,
                                external_id=f"simulated:{event.id}", observed_at=doc.observed_at))
        session.add(Mention(document_id=doc.id, event_id=event.id, similarity=1,
                            human_verified=False, method="simulated_own_coverage"))


def seed(session, now, base_url, reset=False, payload=None):
    if reset:
        for table in reversed(Base.metadata.sorted_tables):
            if table.name not in ("users", "sessions"):
                session.execute(delete(table))
        session.expire_all()
    initialize_config(session)
    session.flush()
    config = session.get(ConfigVersion, session.get(State, "active_config").value["id"])
    config.payload = {**config.payload, "topic_keywords": TOPIC_KEYWORDS,
                      "run_enabled": False, "ai_enabled": False,
                      "telegram_enabled": False, "manual_coverage_complete_until": now if payload else None}
    if payload:
        import_snapshot(session, payload)
        simulate_coverage(session, now, base_url)
        from .scoring import snapshot

        comparison = snapshot(session, "24h", now)
        session.add(State(key="alert_baseline:24h", value={
            "version": config.id, "healthy": True, "at": now,
            "rows": {str(row["event_id"]): {
                "share": row["reference_share"], "documents": [d["id"] for d in row["documents"]],
                "checkpoint_at": now, "qualified": row["independent_source_count"] >= 3,
            } for row in comparison["rows"]},
        }))
    else:
        for row in catalog():
            session.add(Source(**row))
    state = {"version": VERSION, "at": now, "news_applied": False,
             "snapshot_id": payload["snapshot_id"] if payload else None,
             "captured_at": payload["captured_at"] if payload else None,
             "ready": bool(payload), "simulated_client": "Horizonte Federal"}
    session.add(State(key="demo_scenario", value=state))
    session.flush()
    return state


def load_news(session, now, payload, base_url):
    from .alerts import evaluate_alerts
    from .scoring import compare, snapshot

    state = session.get(State, "demo_scenario")
    if not payload or state.value["snapshot_id"] == payload["snapshot_id"]:
        return {"already_applied": True, "documents_added": 0, "alerts_created": 0,
                "affected_events": [], "message": "Sin novedades"}
    before = {r["event_id"]: r for r in compare(session, now=now)["rows"]}
    count, affected = import_snapshot(session, payload)
    if not state.value["ready"]:
        simulate_coverage(session, payload["captured_at"], base_url)
    config = session.get(ConfigVersion, session.get(State, "active_config").value["id"])
    config.payload = {**config.payload, "manual_coverage_complete_until": payload["captured_at"]}
    after = snapshot(session, "24h", payload["captured_at"])
    alerts = evaluate_alerts(session, after)
    state.value = {**state.value, "news_applied": True, "ready": True,
                   "snapshot_id": payload["snapshot_id"], "captured_at": payload["captured_at"],
                   "at": payload["captured_at"]}
    return {"already_applied": False, "documents_added": count, "alerts_created": alerts,
            "affected_events": [{"event_id": row["event_id"], "label": row["label"],
                                 "before": before.get(row["event_id"], {}).get("reference_share"),
                                 "after": row["reference_share"]}
                                for row in after["rows"] if row["event_id"] in affected][:10]}
