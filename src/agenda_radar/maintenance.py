import time

from sqlalchemy import delete, select

from .collaboration_models import AgentRun, AIRun, ChannelDelivery, EditorialFollowup, SlackThread
from .models import (
    Alert,
    Decision,
    Document,
    DocumentVersion,
    Event,
    IngestRun,
    Job,
    LoginSession,
    Mention,
    Observation,
    OwnCoverage,
    ScoreSnapshot,
    State,
    TrendSample,
)


def maintain(db, now=None):
    now = now or time.time()
    cutoff = now - 90 * 86400
    ops_cutoff = now - 30 * 86400
    collab_cutoff = now - 60 * 86400
    with db.session() as session:
        session.execute(delete(LoginSession).where(LoginSession.expires_at < now))
        session.execute(delete(ScoreSnapshot).where(ScoreSnapshot.as_of < cutoff))
        session.execute(delete(TrendSample).where(TrendSample.captured_at < cutoff))
        session.execute(delete(IngestRun).where(IngestRun.started_at < ops_cutoff))
        session.execute(
            delete(Job).where(Job.status.in_(["done", "failed"]), Job.run_after < ops_cutoff)
        )
        session.execute(delete(AgentRun).where(AgentRun.at < collab_cutoff))
        session.execute(delete(AIRun).where(AIRun.at < collab_cutoff))
        session.execute(
            delete(ChannelDelivery).where(
                ChannelDelivery.status.in_(["sent", "failed", "expired", "revoked", "superseded", "policy_restricted"]),
                ChannelDelivery.created_at < collab_cutoff,
            )
        )
        for state in list(
            session.scalars(
                select(State).where(
                    State.key.like("telegram_handled:%") | State.key.like("event_review:%")
                )
            )
        ):
            if isinstance(state.value, dict) and state.value.get("at", now) < ops_cutoff:
                session.delete(state)
        protected = (
            set(session.scalars(select(Decision.event_id)))
            | set(session.scalars(select(Alert.event_id)))
            | set(session.scalars(select(EditorialFollowup.event_id)))
            | set(session.scalars(select(SlackThread.event_id)))
            | set(session.scalars(select(OwnCoverage.event_id)))
            | {
                eid
                for eid in session.scalars(select(ChannelDelivery.event_id))
                if eid is not None
            }
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
        session.flush()
        active_events = set(session.scalars(select(Mention.event_id))) | {
            pid for pid in session.scalars(select(Event.parent_event_id)) if pid is not None
        }
        orphan_events = [
            eid
            for eid in session.scalars(select(Event.id).where(Event.first_observed_at < cutoff))
            if eid not in active_events and eid not in protected
        ]
        for offset in range(0, len(orphan_events), 300):
            session.execute(delete(Event).where(Event.id.in_(orphan_events[offset : offset + 300])))
    with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.exec_driver_sql("PRAGMA optimize")
    return {
        "documents_removed": len(identifiers),
        "events_removed": len(orphan_events),
        "retention_days": 90,
    }


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
