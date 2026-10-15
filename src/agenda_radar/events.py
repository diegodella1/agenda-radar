from sqlalchemy import select

from .models import Decision, Event, Mention, OwnCoverage
from .security import audit


def merge_events(session, target_id, other_id, actor):
    target, other = session.get(Event, target_id), session.get(Event, other_id)
    if (
        not target
        or not other
        or target_id == other_id
        or "merged" in (target.status, other.status)
    ):
        raise ValueError("Acontecimientos inválidos")
    documents = []
    for mention in session.scalars(select(Mention).where(Mention.event_id == other_id)):
        documents.append(mention.document_id)
        mention.event_id, mention.human_verified, mention.method = target_id, True, "manual_merge"
    for coverage in session.scalars(select(OwnCoverage).where(OwnCoverage.event_id == other_id)):
        coverage.event_id = target_id
    other.status, other.parent_event_id = "merged", target_id
    target.first_observed_at = min(target.first_observed_at, other.first_observed_at)
    target.confidence = 1
    session.add(
        Decision(event_id=target_id, user_id=actor, action="merge", reason=f"Desde {other_id}")
    )
    audit(session, actor, "merge", "event", target_id, {"from": other_id, "documents": documents})


def split_event(session, event_id, document_ids, label, actor):
    event = session.get(Event, event_id)
    mentions = list(session.scalars(select(Mention).where(Mention.event_id == event_id)))
    chosen = set(document_ids)
    if not event or not chosen or not chosen < {m.document_id for m in mentions}:
        raise ValueError("Seleccionar parte de las menciones del acontecimiento")
    new = Event(label=label, topic=event.topic, confidence=1, parent_event_id=event_id)
    session.add(new)
    session.flush()
    for mention in mentions:
        mention.human_verified = True
        if mention.document_id in chosen:
            mention.event_id, mention.method = new.id, "manual_split"
    audit(
        session,
        actor,
        "split",
        "event",
        event_id,
        after={"new_event": new.id, "documents": document_ids},
    )
    session.add(Decision(event_id=event_id, user_id=actor, action="split", reason=label))
    return new.id
