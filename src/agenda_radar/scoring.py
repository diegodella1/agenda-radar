import copy
import math
import threading
import time
from collections import defaultdict
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from .editorial import active_config
from .models import Document, Event, Mention, Observation, OwnCoverage, ScoreSnapshot, Source
from .schemas import EditorialConfig

WINDOWS = {"1h": 3600, "6h": 21600, "24h": 86400, "72h": 259200, "7d": 604800}

_COMPARE_CACHE_LOCK = threading.Lock()
_COMPARE_CACHE: dict[tuple, tuple[float, dict[str, Any]]] = {}
_COMPARE_CACHE_TTL = 15.0


def _compare_watermark(session, window: str, config_version: int) -> tuple | None:
    bind = session.get_bind()
    url = str(getattr(bind, "url", ""))
    if not url or ":memory:" in url:
        return None
    doc_sig = session.execute(select(func.count(Document.id), func.max(Document.id))).one()
    mention_sig = session.execute(select(func.count(Mention.document_id), func.max(Mention.event_id))).one()
    cov_sig = session.execute(select(func.count(OwnCoverage.id), func.max(OwnCoverage.id))).one()
    src_sig = tuple(
        (s.id, s.enabled, s.status, s.scope, s.weight, s.group_name, int(s.last_success or 0))
        for s in session.scalars(select(Source).order_by(Source.id))
    )
    ev_sig = session.execute(
        select(func.count(Event.id), func.sum(Event.status == "merged"))
    ).one()
    return (url, window, config_version, tuple(doc_sig), tuple(mention_sig), tuple(cov_sig), tuple(ev_sig), src_sig)


def source_healthy(source: Source, now: float) -> bool:
    return bool(
        source.enabled
        and source.last_success
        and source.status == "healthy"
        and now - source.last_success <= max(1800, source.poll_interval * 2)
    )


def compare(session, window="24h", config: EditorialConfig | None = None, now=None):
    use_cache = config is None and now is None
    now = now or time.time()
    duration = WINDOWS[window]
    version, active = active_config(session)
    config = config or active
    cache_key = _compare_watermark(session, window, version) if use_cache else None
    if cache_key is not None:
        with _COMPARE_CACHE_LOCK:
            cached = _COMPARE_CACHE.get(cache_key)
            if cached and now - cached[0] <= _COMPARE_CACHE_TTL:
                return copy.deepcopy(cached[1])
    sources = list(session.scalars(select(Source).where(Source.enabled.is_(True))))
    source_by_id = {source.id: source for source in sources}
    reference_sources = [s for s in sources if s.scope == "reference"]
    own_sources = [s for s in sources if s.scope == "own" and s.kind != "manual"]
    healthy_references = [s for s in reference_sources if source_healthy(s, now)]
    own_healthy = bool(own_sources) and all(source_healthy(s, now) for s in own_sources)
    manual_complete = bool(
        config.manual_coverage_complete_until and config.manual_coverage_complete_until >= now
    )
    own_healthy = own_healthy or (not own_sources and manual_complete)
    seen = list(
        session.execute(
            select(
                Document.id,
                Document.title,
                Document.canonical_url,
                Document.publisher,
                Document.group_name,
                Document.channel,
                Document.published_at,
                Document.observed_at,
                Mention.event_id,
                Mention.similarity,
                Mention.human_verified,
                Observation.source_id,
            )
            .join(Mention, Mention.document_id == Document.id)
            .join(Observation, Observation.document_id == Document.id)
            .where(
                func.coalesce(Document.published_at, Document.observed_at) >= now - duration,
                func.coalesce(Document.published_at, Document.observed_at) <= now,
            )
        )
    )
    grouped: dict[int, dict[str, Any]] = defaultdict(
        lambda: {
            "reference": {},
            "own": set(),
            "documents": {},
            "sources": set(),
            "recent": set(),
            "previous": set(),
            "confidence": [],
        }
    )
    for document in seen:
        source = source_by_id.get(document.source_id)
        if source is None:
            continue
        row = grouped[document.event_id]
        row["documents"][document.id] = document
        row["sources"].add(source.id)
        row["confidence"].append(
            document.similarity if document.human_verified else min(0.9, document.similarity)
        )
        if source.scope == "own":
            row["own"].add(document.canonical_url)
        if source.scope != "reference" or not source_healthy(source, now):
            continue
        if document.publisher == "unresolved-google-news":
            continue
        stamp = document.published_at or document.observed_at
        decay = math.exp(-math.log(2) * max(0, now - stamp) / max(3600, duration / 2))
        weight = config.source_weights.get(str(source.id), source.weight) / 100
        if weight <= 0:
            continue
        # Ownership comes from the configured publisher source, never an aggregator.
        group = source.group_name if source.kind != "google_news" else document.group_name
        row["reference"][group] = max(row["reference"].get(group, 0), weight * decay)
        vel_step = min(7200, duration / 2)
        if stamp >= now - vel_step:
            row["recent"].add(group)
        elif stamp >= now - 2 * vel_step:
            row["previous"].add(group)
    for coverage in session.scalars(
        select(OwnCoverage).where(
            OwnCoverage.published_at >= now - duration, OwnCoverage.published_at <= now
        )
    ):
        grouped[coverage.event_id]["own"].add(coverage.url)
    reference_total = sum(sum(row["reference"].values()) for row in grouped.values())
    own_total = sum(len(row["own"]) for row in grouped.values())
    reference_ratio = len(healthy_references) / len(reference_sources) if reference_sources else 0
    reference_valid = len({s.group_name for s in healthy_references}) >= 2 and reference_total > 0
    rows = []
    events_by_id = {
        event.id: event
        for event in session.scalars(select(Event).where(Event.id.in_(list(grouped))))
    }
    for event_id, data in grouped.items():
        event = events_by_id.get(event_id)
        if not event or event.status == "merged":
            continue
        reference_share = (
            100 * sum(data["reference"].values()) / reference_total if reference_valid else None
        )
        own_share = 100 * len(data["own"]) / own_total if own_healthy and own_total else None
        gap = (
            reference_share - own_share
            if reference_share is not None and own_share is not None
            else None
        )
        multiplier = config.topic_priorities.get(event.topic, 1)
        for entity, priority in config.entity_priorities.items():
            if entity.lower() in event.label.lower():
                multiplier *= priority
        geographies = {source_by_id[source_id].country for source_id in data["sources"]}
        geo_multiplier = max((config.geo_priorities.get(geo, 1) for geo in geographies), default=1)
        hour = str(datetime.fromtimestamp(now, ZoneInfo(config.timezone)).hour)
        multiplier *= geo_multiplier * config.hourly_priorities.get(hour, 1)
        affinity = multiplier / (1 + multiplier)
        diversity = len(data["reference"])
        confidence = min(event.confidence, min(data["confidence"], default=0.6), reference_ratio)
        velocity = (len(data["recent"]) - len(data["previous"])) / max(1, len(data["previous"]))
        excluded = any(term.lower() in event.label.lower() for term in config.excluded_terms)
        priority = (
            0.35 * max(0, gap or 0) / 100
            + 0.25 * affinity
            + 0.20 * max(0, min(1, velocity))
            + 0.20 * min(1, diversity / 5)
        )
        rows.append(
            {
                "event_id": event_id,
                "label": event.label,
                "topic": event.topic,
                "geographies": sorted(geographies),
                "channels": sorted({d.channel for d in data["documents"].values()}),
                "reference_share": reference_share,
                "own_share": own_share,
                "gap_pp": gap,
                "own_covered": bool(data["own"]),
                "independent_source_count": diversity,
                "confidence": confidence,
                "priority": 0 if excluded else priority,
                "excluded": excluded,
                "requires_review": any(
                    term.lower() in event.label.lower() for term in config.review_terms
                ),
                "velocity": velocity,
                "velocity_method": (
                    "2h_vs_previous_2h_unadjusted"
                    if duration >= 14400
                    else f"{int(duration // 120)}m_vs_previous_{int(duration // 120)}m_unadjusted"
                ),
                "source_ids": sorted(data["sources"]),
                "editorial_multiplier": multiplier,
                "editorial_affinity": affinity,
                "components": {
                    "group_contributions": data["reference"],
                    "reference_denominator": reference_total,
                    "own_denominator": own_total,
                },
                "documents": [
                    {
                        "id": d.id,
                        "title": d.title,
                        "url": d.canonical_url,
                        "publisher": d.publisher,
                        "published_at": d.published_at,
                        "observed_at": d.observed_at,
                    }
                    for d in data["documents"].values()
                ],
            }
        )
    previous: dict[int, ScoreSnapshot] = {}
    for past in session.scalars(
        select(ScoreSnapshot)
        .where(
            ScoreSnapshot.window == window,
            ScoreSnapshot.as_of <= now - duration,
            ScoreSnapshot.as_of >= now - duration - 600,
        )
        .order_by(ScoreSnapshot.as_of.desc())
    ):
        previous.setdefault(past.event_id, past)
    for row in rows:
        past = previous.get(row["event_id"])
        before = past.payload.get("reference_share") if past else None
        row["delta_reference_pp"] = (
            row["reference_share"] - before
            if before is not None and row["reference_share"] is not None
            else None
        )
        row["delta_config_changed"] = bool(past and past.config_version != version)
    rows.sort(key=lambda row: row["priority"], reverse=True)
    result = {
        "window": window,
        "as_of": now,
        "unit": "share_of_observed_attention_pct",
        "algorithm_version": "salience-0.1",
        "config_version": version,
        "source_health": {
            "own": "healthy" if own_healthy else "insufficient",
            "reference": "healthy" if reference_ratio == 1 else "partial",
        },
        "reference_healthy_ratio": reference_ratio,
        "sources_unavailable": [s.id for s in sources if not source_healthy(s, now)],
        "sample_caveat": "Solo fuentes configuradas. Búsquedas y redes no equivalen a cobertura periodística.",
        "limitations": (
            ["Sin distribución propia válida"] if not own_healthy or not own_total else []
        )
        + ["Velocidad heurística sin ajuste por franja horaria"],
        "rows": rows,
    }
    if cache_key is not None:
        with _COMPARE_CACHE_LOCK:
            if len(_COMPARE_CACHE) > 32:
                _COMPARE_CACHE.clear()
            _COMPARE_CACHE[cache_key] = (now, copy.deepcopy(result))
    return result


def snapshot(session, window="24h", now=None):
    result = compare(session, window, now=now)
    for row in result["rows"]:
        session.add(
            ScoreSnapshot(
                event_id=row["event_id"],
                window=window,
                as_of=result["as_of"],
                config_version=result["config_version"],
                payload={
                    **row,
                    "sources_unavailable": result["sources_unavailable"],
                    "source_health": result["source_health"],
                    "unit": result["unit"],
                },
            )
        )
    return result
