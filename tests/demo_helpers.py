"""Offline fixtures only; never installed or shipped as the public corpus."""

import copy
import time

from sqlalchemy import select

from agenda_radar.db import Database
from agenda_radar.demo_corpus import atomic_json, build_snapshot, sync_catalog
from agenda_radar.editorial import initialize_config
from agenda_radar.ingest import store_document
from agenda_radar.models import Source, TrendSample
from agenda_radar.schemas import DocumentInput

STORIES = [
    "Transporte urbano: revisan las frecuencias del corredor sur",
    "Economía local: comercios presentan una nueva feria regional",
    "Salud: hospitales amplían los turnos de atención primaria",
    "Educación: universidades abren becas para estudiantes",
    "Ambiente: comienza el monitoreo del agua del río",
    "Deportes: clubes barriales organizan un torneo juvenil",
    "Trenes nocturnos conectan localidades alejadas",
    "Cooperativas acuerdan distribución mayorista",
    "Centros vecinales organizan campaña preventiva",
    "Escuelas inauguran talleres tecnológicos",
    "Municipios presentan programa de reciclaje",
    "Atletas preparan encuentro internacional",
    "Reparación de estaciones ferroviarias",
    "Productores revisan costos agrícolas",
    "Equipos rurales recorren localidades",
    "Bibliotecas amplían espacios literarios",
    "Organizaciones recuperan humedal urbano",
    "Servicios públicos convocan mesa paritaria",
]


def prepare_corpus(directory):
    now = time.time()
    db = Database(directory / "fixture.db")
    db.migrate()
    with db.session() as session:
        initialize_config(session)
        sync_catalog(session)
        session.flush()
        sources = list(session.scalars(select(Source).where(Source.scope == "reference")))
        for source in sources:
            source.status, source.last_success = "healthy", now
            for i, label in enumerate(STORIES):
                store_document(session, source, DocumentInput(
                    title=label, url=source.options["website"] + f"test-{i}",
                    external_id=f"test-{i}", published_at=now - (i + 1) * 30,
                    excerpt="Contenido de prueba, no utilizado en producción.",
                ), now=now - (i + 1) * 30)
        trends = session.scalar(select(Source).where(Source.kind == "google_trends"))
        trends.status, trends.last_success = "healthy", now
        session.add(TrendSample(source_id=trends.id, label="transporte", value="100+",
                                unit="volume_bucket", captured_at=now, source_url=trends.url))
        session.flush()
        payload = build_snapshot(session, now)
    db.engine.dispose()
    atomic_json(directory / "public" / "latest.json", payload)
    return payload


def publish_news(directory, payload):
    updated = copy.deepcopy(payload)
    updated["captured_at"] += 30
    updated["snapshot_id"] += "-news"
    doc = copy.deepcopy(updated["documents"][0])
    doc["item"].update(url="https://www.lanacion.com.ar/test-new", external_id="test-new",
                       title="Transporte urbano: revisan las frecuencias del corredor sur")
    doc["observed_at"] = doc["ingested_at"] = updated["captured_at"]
    updated["documents"].append(doc)
    atomic_json(directory / "public" / "latest.json", updated)
    return updated
