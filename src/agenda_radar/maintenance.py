import time

from sqlalchemy import delete, select

from .models import (
    Alert,
    Decision,
    Document,
    DocumentVersion,
    LoginSession,
    Mention,
    Observation,
    ScoreSnapshot,
    TrendSample,
)


def maintain(db, now=None):
    now = now or time.time()
    cutoff = now - 90 * 86400
    with db.session() as session:
        session.execute(delete(LoginSession).where(LoginSession.expires_at < now))
        session.execute(delete(ScoreSnapshot).where(ScoreSnapshot.as_of < cutoff))
        session.execute(delete(TrendSample).where(TrendSample.captured_at < cutoff))
        protected = set(session.scalars(select(Decision.event_id))) | set(
            session.scalars(select(Alert.event_id))
        )
        candidates = list(
            session.execute(
                select(Document.id, Mention.event_id)
                .join(Mention)
                .where(Document.observed_at < cutoff)
            ).all()
        )
        identifiers = [
            document_id for document_id, event_id in candidates if event_id not in protected
        ]
        for offset in range(0, len(identifiers), 300):
            batch = identifiers[offset : offset + 300]
            for model in (Observation, DocumentVersion, Mention):
                session.execute(delete(model).where(model.document_id.in_(batch)))
            session.execute(delete(Document).where(Document.id.in_(batch)))
    with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.exec_driver_sql("PRAGMA wal_checkpoint(PASSIVE)")
        connection.exec_driver_sql("PRAGMA optimize")
    return {"documents_removed": len(identifiers), "retention_days": 90}


def rotate_backups(directory):
    """Keep latest backup for seven days and four ISO weeks; ignore foreign files."""
    import re
    from datetime import date as CalendarDate
    from datetime import datetime, timezone
    from pathlib import Path

    candidates = []
    for path in directory.glob("agenda-*.db"):
        match = re.fullmatch(r"agenda-(\d{19})\.db", path.name)
        if not match or not path.with_suffix(".sha256").exists():
            continue
        stamp = int(match.group(1)) / 1_000_000_000
        candidates.append((stamp, path))
    days: set[CalendarDate] = set()
    weeks: set[tuple[int, int]] = set()
    keep: set[Path] = set()
    for stamp, path in sorted(candidates, reverse=True):
        date = datetime.fromtimestamp(stamp, timezone.utc)
        day = date.date()
        week = date.isocalendar()[:2]
        if day not in days and len(days) < 7:
            days.add(day)
            keep.add(path)
        if week not in weeks and len(weeks) < 4:
            weeks.add(week)
            keep.add(path)
    for _, path in candidates:
        if path not in keep:
            path.unlink()
            path.with_suffix(".sha256").unlink()
    return len(keep)
