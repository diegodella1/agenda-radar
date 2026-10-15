"""Synthetic benchmark; separate DB, no external sources or credentials."""

import json
import resource
import statistics
import time
from pathlib import Path

from sqlalchemy import insert

from agenda_radar.db import Database
from agenda_radar.editorial import initialize_config
from agenda_radar.models import Document, Event, Mention, Observation, Source
from agenda_radar.scoring import compare

root = Path("artifacts/benchmark")
root.mkdir(parents=True, exist_ok=True)
path = root / "agenda.db"
existing = path.exists()
db = Database(path)
db.migrate()
now = time.time()
if not existing:
    with db.session() as session:
        initialize_config(session)
        session.execute(
            insert(Source),
            [
                dict(
                    id=i + 1,
                    name=f"Synthetic source {i}",
                    url=f"https://s{i}.example/rss",
                    kind="rss",
                    scope="own" if i == 29 else "reference",
                    group_name=f"group-{i}",
                    legal_basis="Synthetic benchmark",
                    status="healthy",
                    last_success=now,
                )
                for i in range(30)
            ],
        )
        session.execute(
            insert(Event),
            [dict(id=i + 1, label=f"Synthetic event {i}", confidence=0.9) for i in range(500)],
        )
        for start in range(0, 10000, 500):
            session.execute(
                insert(Document),
                [
                    dict(
                        id=i + 1,
                        publisher=f"s{i % 30}.example",
                        group_name=f"group-{i % 30}",
                        canonical_url=f"https://s{i % 30}.example/{i}",
                        title=f"Synthetic event {i // 20} mention {i}",
                        excerpt="Synthetic benchmark excerpt",
                        content_hash=str(i),
                        published_at=now - 600,
                        observed_at=now - 590,
                    )
                    for i in range(start, start + 500)
                ],
            )
            session.execute(
                insert(Mention),
                [
                    dict(document_id=i + 1, event_id=i // 20 + 1, similarity=0.9)
                    for i in range(start, start + 500)
                ],
            )
            session.execute(
                insert(Observation),
                [
                    dict(document_id=i + 1, source_id=i % 30 + 1, external_id=str(i))
                    for i in range(start, start + 500)
                ],
            )
latencies = []
for _ in range(10):
    start = time.perf_counter()
    with db.session() as session:
        result = compare(session, now=now)
    latencies.append(time.perf_counter() - start)
report = {
    "synthetic": True,
    "documents": 10000,
    "sources": 30,
    "events": len(result["rows"]),
    "iterations": len(latencies),
    "p50_seconds": statistics.median(latencies),
    "p95_seconds": sorted(latencies)[-1],
    "peak_process_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    "note": "Service computation only; not HTTP dashboard p95 or 24h soak.",
}
(root / "result.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
