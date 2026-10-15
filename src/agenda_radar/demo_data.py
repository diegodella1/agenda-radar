"""Versioned fictional newsroom. No network, providers or production data."""

import hashlib

from sqlalchemy import delete, select

from .alerts import RULE_LABELS, evaluate_alerts
from .editorial import initialize_config
from .models import (
    Alert,
    Base,
    ConfigVersion,
    Decision,
    Document,
    Event,
    Mention,
    Observation,
    ScoreSnapshot,
    Source,
    State,
    TrendSample,
    User,
)
from .scoring import compare

VERSION = "argentina-v1"
STORIES = [
    ("Transporte urbano: revisan las frecuencias del corredor sur", "transporte", 0.1),
    ("Economía local: comercios presentan una nueva feria regional", "economía", 0.25),
    ("Salud: hospitales amplían los turnos de atención primaria", "salud", 0.4),
    ("Educación: universidades abren becas para estudiantes", "educación", 0.5),
    ("Ambiente: comienza el monitoreo del agua del río", "ambiente", 1.5),
    ("Deportes: clubes barriales organizan un torneo juvenil", "deportes", 3),
    ("Transporte: vecinos proponen nuevos recorridos nocturnos", "transporte", 5),
    ("Economía: cooperativas acuerdan una red de distribución", "economía", 8),
    ("Salud: centros vecinales preparan una campaña preventiva", "salud", 12),
    ("Educación: escuelas inauguran talleres de tecnología", "educación", 18),
    ("Ambiente: municipios presentan un programa de reciclaje", "ambiente", 22),
    ("Deportes: atletas locales preparan el encuentro regional", "deportes", 30),
    ("Transporte: avanza la reparación de estaciones ferroviarias", "transporte", 40),
    ("Economía: productores revisan los costos de la cosecha", "economía", 55),
    ("Salud: equipos rurales coordinan visitas a localidades", "salud", 65),
    ("Educación: bibliotecas amplían los espacios de lectura", "educación", 90),
    ("Ambiente: organizaciones recuperan un humedal urbano", "ambiente", 120),
    ("Transporte: anuncian una mesa de diálogo por los servicios", "transporte", 0.2),
]
MEDIA = [
    "DEMO · Horizonte Federal",
    "DEMO · La Plaza",
    "DEMO · Punto Interior",
    "DEMO · Mirada Sur",
    "DEMO · Cuaderno Público",
    "DEMO · Litoral Abierto",
    "DEMO · Nuestra Redacción",
]


def add_document(session, source, event, now, age, suffix, base_url):
    session.flush()
    doc = Document(
        publisher=source.name,
        group_name=source.group_name,
        canonical_url=f"{base_url}/evidence/pending-{suffix}",
        title=f"{event.label} · {source.name}",
        excerpt=(
            "Escenario ficticio de Agenda Radar. " + event.label + ". "
            "El equipo consulta a vecinos y especialistas, revisa los antecedentes y "
            "prepara preguntas para la próxima reunión editorial. "
            "Este texto no describe hechos reales ni representa a un medio existente."
        ),
        content_hash=hashlib.sha256(suffix.encode()).hexdigest(),
        topic=event.topic,
        channel=source.channel,
        published_at=now - age * 3600,
        observed_at=now - age * 3600,
        ingested_at=now - age * 3600,
    )
    session.add(doc)
    session.flush()
    doc.canonical_url = f"{base_url}/evidence/{doc.id}"
    session.add(
        Observation(
            source_id=source.id, document_id=doc.id, external_id=suffix, observed_at=doc.observed_at
        )
    )
    session.add(
        Mention(
            document_id=doc.id,
            event_id=event.id,
            similarity=0.95,
            human_verified=True,
            method="synthetic_fixture",
        )
    )
    return doc


def seed(session, now, base_url, reset=False):
    if reset:
        # Keep only authentication; visit requests are serialized during reset.
        for table in reversed(Base.metadata.sorted_tables):
            if table.name not in ("users", "sessions"):
                session.execute(delete(table))
        session.expire_all()
    initialize_config(session)
    session.flush()
    config = session.get(ConfigVersion, session.get(State, "active_config").value["id"])
    config.payload = {
        **config.payload,
        "run_enabled": False,
        "minimum_gap_pp": 5,
        "priority_threshold": 0.4,
        "agenda_shift_pp": 3,
        "topic_priorities": {"transporte": 2, "salud": 1.5},
    }
    sources = []
    for i, name in enumerate(MEDIA):
        source = Source(
            name=name,
            url=f"https://medio-{i}.example/feed",
            kind="rss",
            scope="own" if i == 6 else "reference",
            group_name=f"Grupo ficticio {i}",
            channel="video" if i == 5 else "web",
            country="UY" if i == 5 else "AR",
            legal_basis="Contenido sintético de demostración, sin recolección externa",
            status="healthy",
            last_success=now,
            next_poll=now + 86400,
            poll_interval=86400,
        )
        session.add(source)
        sources.append(source)
    events = []
    for i, (label, topic, age) in enumerate(STORIES):
        event = Event(label=label, topic=topic, confidence=0.95, first_observed_at=now - age * 3600)
        session.add(event)
        session.flush()
        events.append(event)
        count = 2 if i == 17 else 6 if i < 6 else 5
        for j, source in enumerate(sources[:count]):
            add_document(session, source, event, now, age + j * 0.005, f"initial-{i}-{j}", base_url)
        if i in (1, 2, 3, 5, 7, 9, 11, 13, 15, 16):
            add_document(session, sources[6], event, now, age, f"own-{i}", base_url)
    session.flush()
    result = compare(session, now=now)
    rows = {r["event_id"]: r for r in result["rows"]}
    for i, rule in enumerate(RULE_LABELS):
        row = rows[events[i].id]
        session.add(
            Alert(
                event_id=events[i].id,
                rule=rule,
                dedupe_key=f"fixture-{rule}",
                at=now - 1800 - i * 60,
                payload={
                    **row,
                    "rule_label": RULE_LABELS[rule],
                    "demo_historical": True,
                    "trigger_metric": row["gap_pp"],
                },
            )
        )
    user_id = session.scalar(select(User.id))
    for i, action in ((1, "follow"), (2, "accept"), (5, "review")):
        session.add(
            Decision(
                event_id=events[i].id,
                user_id=user_id,
                action=action,
                reason="Ejemplo ficticio: contrastar evidencia en el pase de redacción.",
                at=now - 900,
            )
        )
    for i in (0, 3, 4):
        session.add(
            TrendSample(
                source_id=sources[i].id,
                label=events[i].label,
                value=str(90 - i * 10),
                unit="índice ficticio",
                captured_at=now,
                source_url=f"{base_url}/events/{events[i].id}",
            )
        )
    for row in result["rows"]:
        session.add(
            ScoreSnapshot(
                event_id=row["event_id"],
                window="24h",
                as_of=now - 86400,
                config_version=config.id,
                algorithm_version="demo-historical",
                payload={"reference_share": max(0, row["reference_share"] - 2)},
            )
        )
    # Initial historical alerts are explicitly fictional; new alerts use real rules.
    session.add(
        State(
            key="alert_baseline:24h",
            value={
                "version": config.id,
                "healthy": True,
                "at": now,
                "rows": {
                    str(r["event_id"]): {
                        "share": r["reference_share"],
                        "documents": [d["id"] for d in r["documents"]],
                        "checkpoint_at": now,
                        "qualified": r["independent_source_count"] >= 3,
                    }
                    for r in result["rows"]
                },
            },
        )
    )
    session.add(
        State(
            key="demo_scenario",
            value={
                "version": VERSION,
                "at": now,
                "news_applied": False,
                "target_event": events[0].id,
                "emerging_event": events[17].id,
            },
        )
    )
    session.add(State(key="worker_heartbeat", value={"at": now}))
    return {"version": VERSION, "events": len(events)}


def simulate_news(session, now, base_url):
    state = session.get(State, "demo_scenario")
    if state.value["news_applied"]:
        return {"already_applied": True, "documents_added": 0, "alerts_created": 0}
    sources = list(
        session.scalars(select(Source).where(Source.scope == "reference").order_by(Source.id))
    )
    target = session.get(Event, state.value["target_event"])
    emerging = session.get(Event, state.value["emerging_event"])
    if not target or not emerging or target.status == "merged" or emerging.status == "merged":
        raise ValueError("El escenario cambió. Reiniciá la demo para simular este lote.")
    for i, source in enumerate(sources[:6]):
        add_document(session, source, target, now, 0.01, f"news-{i}", base_url)
    for i, source in enumerate(sources[2:6]):
        add_document(session, source, emerging, now, 0.01, f"emerging-{i}", base_url)
    session.flush()
    count = evaluate_alerts(session, compare(session, now=now))
    state.value = {**state.value, "news_applied": True}
    return {
        "already_applied": False,
        "documents_added": min(6, len(sources)) + len(sources[2:6]),
        "alerts_created": count,
    }
