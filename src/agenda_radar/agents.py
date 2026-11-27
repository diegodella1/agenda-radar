"""Bounded editorial agents, human decisions, and channel-independent delivery records."""
import hashlib
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from .collaboration_models import (
    AgentRun,
    AIProfile,
    ChannelDelivery,
    EditorialAgent,
    EditorialFollowup,
)
from .data_policy import permitted_evidence
from .models import Alert, Decision, Document, Event, Mention, State, User
from .security import ROLES, audit


def slack_config(session):
    row = session.get(State, 'slack_config')
    return row.value if row else {'enabled': False, 'team_id': '', 'channels': {}, 'quiet_start': 23, 'quiet_end': 7}


def decide(session, user_id, event_id, action, reason='', key=None):
    user, event = session.get(User, user_id), session.get(Event, event_id)
    if not user or not user.enabled or ROLES[user.role] < ROLES['editor']:
        raise ValueError('editor_permission_required')
    if not event:
        raise ValueError('event_not_found')
    if action not in ('follow', 'dismiss', 'claim', 'mute', 'complete', 'useful', 'noise'):
        raise ValueError('invalid_editorial_action')
    if action in ('dismiss', 'noise') and not reason.strip():
        raise ValueError('reason_required')
    if key:
        result = session.execute(insert(State).values(key='decision:'+key, value={}).on_conflict_do_nothing())
        if not result.rowcount:
            return
    follow = session.get(EditorialFollowup, event_id) or EditorialFollowup(event_id=event_id)
    if action == 'claim':
        if follow.owner_id and follow.owner_id != user_id:
            raise ValueError('already_assigned')
        follow.owner_id, follow.status = user_id, 'following'
    elif action in ('follow', 'dismiss', 'complete'):
        follow.status = {'follow': 'following', 'dismiss': 'dismissed', 'complete': 'completed'}[action]
    elif action == 'mute':
        follow.muted_until = time.time() + 7200
    follow.updated_at = time.time()
    session.add(follow)
    session.add(Decision(event_id=event_id, user_id=user_id, action=action, reason=reason[:2000]))
    audit(session, user_id, action, 'event', event_id)


def evidence_for_event(session, event_id, source_ids=None):
    documents = session.scalars(select(Document).join(Mention).where(Mention.event_id == event_id).order_by(Document.observed_at.desc()).limit(40))
    items = [{'id': doc.id, 'title': doc.title, 'excerpt': doc.excerpt[:800], 'url': doc.canonical_url,
              'observed_at': doc.observed_at, 'hash': doc.content_hash} for doc in documents]
    return permitted_evidence(session, items, 'external', source_ids)


def build_preview(db, agent_id):
    from .scoring import WINDOWS
    with db.session() as session:
        agent = session.get(EditorialAgent, agent_id)
        if not agent:
            raise ValueError('agent_not_found')
        from .scoring import compare
        ranking = {row['event_id']: row['priority'] for row in compare(session, agent.window)['rows']}
        since = time.time() - WINDOWS[agent.window]
        events = list(session.scalars(select(Event).where(Event.status == 'active').order_by(Event.id.desc()).limit(200)))
        events.sort(key=lambda event: ranking.get(event.id, 0), reverse=True)
        alerts = set(session.scalars(select(Alert.event_id).where(Alert.at >= since)))
        items = []
        for event in events:
            follow = session.get(EditorialFollowup, event.id)
            if follow and (follow.status in ('dismissed', 'completed') or follow.muted_until > time.time()):
                continue
            if agent.topics and event.topic not in agent.topics:
                continue
            if agent.kind == 'vigilance' and event.id not in alerts:
                continue
            if agent.kind == 'followup' and (not follow or follow.status != 'following'):
                continue
            evidence = [item for item in evidence_for_event(session, event.id, agent.source_ids) if item['observed_at'] >= since]
            if not evidence:
                continue
            signature = hashlib.sha256(json.dumps([(item['id'], item['hash']) for item in evidence], sort_keys=True).encode()).hexdigest()
            if agent.kind != 'briefing' and agent.state.get(str(event.id)) == signature:
                continue
            items.append({'event_id': event.id, 'title': evidence[0]['title'], 'evidence': evidence[:5],
                          'signature': signature, 'language': agent.language,
                          'reason': ('New evidence to review' if agent.language == 'en' else 'Nueva evidencia para revisar'),
                          'owner_id': follow.owner_id if follow else None})
            if len(items) >= agent.max_items:
                break
        return {'agent_id': agent.id, 'kind': agent.kind, 'language': agent.language,
                'preview': True, 'as_of': time.time(), 'window': agent.window, 'items': items,
                'notice': 'Only sources explicitly allowed for external sharing are included.' if agent.language == 'en' else 'Solo se incluyen fuentes autorizadas para compartir externamente.'}


def run_agent(db, vault, agent_id, preview=True):
    from .assistant import profile_answer
    from .editorial import active_config
    result = build_preview(db, agent_id)
    with db.session() as session:
        agent = session.get(EditorialAgent, agent_id)
        profile = session.get(AIProfile, agent.profile_id) if agent.profile_id else None
        _, config = active_config(session)
        connection = slack_config(session)
        if not preview and (not agent.enabled or not connection.get('enabled') or agent.channel_id not in connection.get('channels', {})):
            raise ValueError('agent_delivery_disabled')
    if profile and config.ai_enabled:
        for item in result['items']:
            answer = profile_answer(db, vault, profile, 'Summarize the new evidence and its limitations.',
                                    item['evidence'], agent.language)
            item['summary'] = answer['answer']
            item['mode'] = answer['mode']
    result['preview'] = preview
    with db.session() as session:
        agent = session.get(EditorialAgent, agent_id)
        connection = slack_config(session)
        if not preview and (not agent.enabled or not connection.get('enabled') or agent.channel_id not in connection.get('channels', {})):
            raise ValueError('agent_delivery_disabled')
        session.add(AgentRun(agent_id=agent.id, preview=preview, result=result))
        if preview:
            return result
        state = dict(agent.state)
        if agent.kind == 'briefing':
            state['_briefing_day'] = datetime.now(ZoneInfo(agent.timezone)).date().isoformat()
        for item in result['items']:
            day = datetime.now(ZoneInfo(agent.timezone)).date().isoformat() if agent.kind == 'briefing' else ''
            key = f"agent:{agent.id}:{item['event_id']}:{item['signature']}:{day}"
            session.execute(insert(ChannelDelivery).values(
                dedupe_key=key, destination=agent.channel_id, event_id=item['event_id'],
                payload=item, expires_at=time.time()+21600).on_conflict_do_nothing())
            state[str(item['event_id'])] = item['signature']
        agent.state = state
    return result


def due_agents(db):
    now = time.time()
    with db.session() as session:
        config = slack_config(session)
        if not config.get('enabled'):
            return []
        result = []
        for agent in session.scalars(select(EditorialAgent).where(EditorialAgent.enabled.is_(True), EditorialAgent.next_run <= now)):
            local = datetime.now(ZoneInfo(agent.timezone))
            if agent.kind == 'briefing' and (local.hour < agent.hour or agent.state.get('_briefing_day') == local.date().isoformat()):
                continue
            result.append(agent.id)
            agent.next_run = now + (3600 if agent.kind == 'briefing' else 300)
        return result
