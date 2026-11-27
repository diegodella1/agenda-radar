"""Shared collector. Only public corpus rows cross into visitor databases."""

import fcntl
import hashlib
import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path

from sqlalchemy import delete, select

from .db import Database
from .demo_catalog import VERSION, catalog
from .editorial import initialize_config
from .ingest import poll_source
from .models import (
    Document,
    DocumentVersion,
    Event,
    IngestRun,
    Mention,
    Observation,
    Source,
    TrendSample,
)
from .network import FetchError, check_robots, fetch
from .scoring import source_healthy
from .security import Vault

log = logging.getLogger(__name__)


def atomic_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".snapshot-")
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(payload, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_snapshot(directory):
    try:
        payload = json.loads((Path(directory) / "public" / "latest.json").read_text())
        if payload.get("version") == VERSION and payload.get("ready"):
            return payload
    except (OSError, ValueError, TypeError):
        pass
    return None


def sync_catalog(session):
    existing = {s.options.get("catalog_id"): s for s in session.scalars(select(Source))}
    for entry in catalog():
        key = entry["options"]["catalog_id"]
        if key not in existing:
            session.add(Source(**entry))
        else:
            source = existing[key]
            # Preserve resolved IDs, validators, quota state, and operator-disabled sources.
            source.options = {**source.options, **entry["options"]}
            source.poll_interval = entry["poll_interval"]
            source.name, source.group_name = entry["name"], entry["group_name"]
            if source.channel in ("web", "video") and (source.url != entry["url"] or source.kind != entry["kind"]):
                source.url, source.kind = entry["url"], entry["kind"]
                source.enabled, source.status, source.error_code = True, "pending", None
                source.etag, source.modified, source.next_poll = None, None, 0


def resolve_channels(db, vault):
    with db.session() as session:
        sources = list(session.scalars(select(Source)))
        token = vault.get(session, "x")
    for source in sources:
        try:
            if source.channel == "video" and not source.options.get("channel_id"):
                profile = source.options["profiles"]["youtube"]
                match = re.search(r"/channel/(UC[\w-]{22})(?:/|$)", profile)
                if not match:
                    check_robots(profile)
                    body = fetch(profile).body.decode("utf-8", errors="replace")
                    match = re.search(r'"(?:externalId|channelId)"\s*:\s*"(UC[\w-]{22})"', body)
                if not match:
                    raise FetchError("youtube_channel_id_required")
                identifier = match[1]
                with db.session() as session:
                    row = session.get(Source, source.id)
                    row.options = {**row.options, "channel_id": identifier}
                    row.url = f"https://www.youtube.com/feeds/videos.xml?channel_id={identifier}"
                    row.enabled, row.status, row.error_code = True, "pending", None
            elif source.kind == "x" and not source.options.get("user_id"):
                if not token:
                    raise FetchError("no_credentials")
                from .x_connector import resolve_user

                identifier = resolve_user(source.options["username"], token)
                with db.session() as session:
                    row = session.get(Source, source.id)
                    row.options = {**row.options, "user_id": identifier}
                    row.enabled = True
        except FetchError as exc:
            with db.session() as session:
                row = session.get(Source, source.id)
                row.status, row.error_code = "pending", exc.code


def prune(session, now):
    cutoff = now - 7 * 86400
    identifiers = select(Document.id).where(Document.observed_at < cutoff)
    for model in (DocumentVersion, Observation, Mention):
        session.execute(delete(model).where(model.document_id.in_(identifiers)))
    session.execute(delete(Document).where(Document.observed_at < cutoff))
    session.execute(delete(Event).where(~Event.id.in_(select(Mention.event_id))))
    session.execute(delete(TrendSample).where(TrendSample.captured_at < cutoff))
    session.execute(delete(IngestRun).where(IngestRun.started_at < cutoff))


def build_snapshot(session, now):
    sources = list(session.scalars(select(Source).order_by(Source.id)))
    source_rows = [{c.name: getattr(s, c.name) for c in Source.__table__.columns} for s in sources]
    documents = []
    media, regions = set(), set()
    by_id = {s.id: s for s in sources}
    for doc, observation in session.execute(
        select(Document, Observation).join(Observation, Observation.document_id == Document.id)
        .where(Document.observed_at >= now - 7 * 86400).order_by(Document.observed_at, Document.id)
    ):
        source = by_id[observation.source_id]
        if source.scope == "reference" and source_healthy(source, now):
            media.add(source.options["catalog_id"])
            regions.add(source.options["region"])
        documents.append({"source_key": source.options["catalog_id"],
                          "observed_at": doc.observed_at, "ingested_at": doc.ingested_at,
                          "item": {"url": doc.canonical_url, "title": doc.title,
                                   "excerpt": doc.excerpt[:500], "published_at": doc.published_at,
                                   "external_id": observation.external_id}})
    trends = [{"source_key": by_id[t.source_id].options["catalog_id"],
               **{k: getattr(t, k) for k in ("label", "geo", "value", "unit", "captured_at", "source_url")}}
              for t in session.scalars(select(TrendSample).order_by(TrendSample.id))]
    fresh_trends = any(t["captured_at"] >= now - 4500 for t in trends)
    ready = len(media) >= 6 and len(regions) >= 4 and fresh_trends
    payload = {"version": VERSION, "captured_at": now, "ready": ready,
               "media_count": len(media), "regions": sorted(regions),
               "sources": source_rows, "documents": documents, "trends": trends}
    payload["snapshot_id"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return payload


def collect_once(directory, *, discover=False, force=False):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / "collector.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        db = Database(directory / "collector.db")
        try:
            db.migrate()
            vault = Vault(directory / "secrets")
            vault.initialize()
            with db.session() as session:
                initialize_config(session)
                sync_catalog(session)
            if discover:
                resolve_channels(db, vault)
            with db.session() as session:
                due = list(session.scalars(select(Source.id).where(
                    Source.enabled.is_(True), Source.next_poll <= (float("inf") if force else time.time())
                )))
            for source_id in due:
                try:
                    poll_source(db, source_id, vault)
                except FetchError as exc:
                    log.warning("demo_source_failed id=%s code=%s", source_id, exc.code)
            now = time.time()
            with db.session() as session:
                prune(session, now)
                payload = build_snapshot(session, now)
            atomic_json(directory / "public" / "status.json", {k: v for k, v in payload.items() if k not in ("documents", "trends")})
            if payload["ready"]:
                previous = read_snapshot(directory)
                if previous:
                    atomic_json(directory / "public" / "previous.json", previous)
                atomic_json(directory / "public" / "latest.json", payload)
            return {"ready": payload["ready"], "media_count": payload["media_count"],
                    "regions": payload["regions"], "documents": len(payload["documents"]),
                    "trends": len(payload["trends"])}
        finally:
            db.engine.dispose()


def run(directory):
    next_discovery = 0.0
    while True:
        try:
            discover = time.time() >= next_discovery
            collect_once(directory, discover=discover)
            if discover:
                next_discovery = time.time() + 86400
        except Exception:
            log.exception("demo_collection_failed")
        time.sleep(3600)
