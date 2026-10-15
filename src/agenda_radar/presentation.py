"""Shared editorial view. Filters never change scoring denominators."""

from urllib.parse import urlencode

from sqlalchemy import select

from .models import Observation, Source, TrendSample
from .scoring import WINDOWS, compare, source_healthy


def editorial_view(session, window="24h", *, now=None, topic="", source="", channel="", geo=""):
    data = compare(session, window, now=now)
    filters = dict(topic=topic, source=str(source), channel=channel, geo=geo)
    data["filters"] = filters
    data["query"] = urlencode({"window": window, **{k: v for k, v in filters.items() if v}})
    data["universe_count"] = len(data["rows"])
    data["topics"] = sorted({r["topic"] for r in data["rows"]})
    sources = list(session.scalars(select(Source).order_by(Source.name)))
    data["sources"] = [
        {
            "id": s.id,
            "name": s.name,
            "group": s.group_name,
            "scope": s.scope,
            "healthy": source_healthy(s, data["as_of"]),
        }
        for s in sources
    ]
    data["rows"] = [
        r
        for r in data["rows"]
        if (not topic or r["topic"] == topic)
        and (not source or (str(source).isdigit() and int(source) in r["source_ids"]))
        and (not channel or channel in r["channels"])
        and (not geo or geo in r["geographies"])
    ]
    document_ids = {d["id"] for r in data["rows"] for d in r["documents"]}
    observed_sources: dict[int, set[int]] = {}
    if document_ids:
        for doc_id, source_id in session.execute(
            select(Observation.document_id, Observation.source_id).where(
                Observation.document_id.in_(document_ids)
            )
        ):
            observed_sources.setdefault(doc_id, set()).add(source_id)
    interval = min(7200, WINDOWS[window] / 2)
    for row in data["rows"]:
        for document in row["documents"]:
            document["source_ids"] = sorted(observed_sources.get(document["id"], set()))
        stamps = [d["published_at"] or d["observed_at"] for d in row["documents"]]
        recent = sum(data["as_of"] - interval <= stamp <= data["as_of"] for stamp in stamps)
        previous = sum(
            data["as_of"] - 2 * interval <= stamp < data["as_of"] - interval for stamp in stamps
        )
        row["momentum"] = {
            "recent": recent,
            "previous": previous,
            "interval_minutes": int(interval / 60),
            "label": (
                "Más publicaciones"
                if recent > previous
                else "Menos publicaciones"
                if recent < previous
                else "Ritmo estable"
            )
            if previous and recent
            else "Historial insuficiente para comparar",
        }

        row["status"] = (
            "Requiere revisión"
            if row["requires_review"]
            else "Cobertura registrada"
            if row["own_covered"]
            else "Sin cobertura registrada"
        )
        row["confidence_pct"] = round(row["confidence"] * 100)
        row["sources"] = [s for s in data["sources"] if s["id"] in row["source_ids"]]
        row["href"] = f"/events/{row['event_id']}?{data['query']}"
        row["rationale"] = (
            "Excluido por criterio editorial."
            if row["excluded"]
            else f"Afinidad con tu criterio: {round(row['editorial_affinity'] * 100)}%. "
            "La prioridad combina brecha, afinidad editorial, diversidad y velocidad de publicación."
        )
    data["momentum_scale"] = max((max(r["momentum"]["recent"], r["momentum"]["previous"]) for r in data["rows"]), default=1) or 1
    data["topic_summary"] = []
    for name in sorted({r["topic"] for r in data["rows"]}):
        rows = [r for r in data["rows"] if r["topic"] == name]
        data["topic_summary"].append(
            {
                "label": name,
                **{
                    key: sum(r[key] for r in rows)
                    if all(r[key] is not None for r in rows)
                    else None
                    for key in ("reference_share", "own_share")
                },
            }
        )
    data["summary"] = {
        "visible": len(data["rows"]),
        "uncovered": sum(not r["own_covered"] for r in data["rows"]),
        "review": sum(r["requires_review"] for r in data["rows"]),
    }
    data["search_signals"] = [{"label": t.label, "value": t.value, "unit": t.unit,
                               "geo": t.geo, "captured_at": t.captured_at, "url": t.source_url}
                              for t in session.scalars(select(TrendSample).where(
                                  TrendSample.captured_at >= data["as_of"] - WINDOWS[window],
                                  TrendSample.captured_at <= data["as_of"]
                              ).order_by(TrendSample.captured_at.desc()).limit(3))]
    data["x_available"] = any(s.enabled and s.channel == "x" and source_healthy(s, data["as_of"]) for s in sources)
    data["denominator_scope"] = "original_universe"
    return data
