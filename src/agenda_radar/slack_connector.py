"""Slack receives commands only; all queries and notifications use a durable queue."""
import html
import json
import time
from datetime import datetime
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert

from .agents import decide, evidence_for_event, slack_config
from .collaboration_models import ChannelDelivery, EditorialFollowup, SlackIdentity, SlackThread
from .data_policy import permitted_evidence
from .jobs import enqueue
from .models import Document, State, User
from .security import ROLES, audit, digest


def client_for(db, vault):
    from slack_sdk import WebClient
    with db.session() as session:
        token = vault.get(session, 'slack_bot')
    if not token:
        raise ValueError('slack_credentials_required')
    return WebClient(token=token, timeout=10, retry_handlers=[])


def test_connection(db, vault):
    client = client_for(db, vault)
    result = client.auth_test()
    with db.session() as session:
        config = slack_config(session)
        if result['team_id'] != config.get('team_id'):
            raise ValueError('slack_workspace_mismatch')
    return {'ok': True, 'team_id': result['team_id']}


def authorized(session, slack_user, channel):
    config = slack_config(session)
    if not config.get('enabled') or channel not in config.get('channels', {}):
        raise ValueError('slack_channel_not_authorized')
    link = session.scalar(select(SlackIdentity).where(SlackIdentity.slack_user_id == slack_user))
    user = session.get(User, link.user_id) if link else None
    if not user or not user.enabled or ROLES[user.role] < ROLES['editor']:
        raise ValueError('slack_identity_not_authorized')
    return user


def accept_payload(db, payload):
    """Validate identity/channel before putting any question or action on the queue."""
    event = payload.get('event', {})
    channel = payload.get('channel_id') or payload.get('channel', {}).get('id') or event.get('channel')
    slack_user = payload.get('user_id') or payload.get('user', {}).get('id') or event.get('user')
    team = payload.get('team_id') or payload.get('team', {}).get('id')
    with db.session() as session:
        config = slack_config(session)
        if not config.get('enabled') or team != config.get('team_id'):
            raise ValueError('slack_workspace_not_authorized')
        if event.get('bot_id') or event.get('subtype') or (event and event.get('type') != 'app_mention'):
            return None
        text = (payload.get('text') or event.get('text') or '').strip()
        if text.startswith('link '):
            if channel not in config.get('channels', {}):
                raise ValueError('slack_channel_not_authorized')
            link = session.scalar(select(SlackIdentity).where(SlackIdentity.code_hash == digest(text[5:].strip()), SlackIdentity.expires_at > time.time()))
            if not link or not (user := session.get(User, link.user_id)) or not user.enabled:
                raise ValueError('invalid_pairing_code')
            existing = session.scalar(select(SlackIdentity).where(SlackIdentity.slack_user_id == slack_user))
            if existing and existing.user_id != user.id:
                raise ValueError('slack_identity_already_linked')
            link.slack_user_id, link.code_hash, link.expires_at = slack_user, None, 0
            audit(session, user.id, 'pair', 'slack')
            return {'paired': True}
        if payload.get('type') == 'view_submission':
            metadata = json.loads(payload['view']['private_metadata'])
            channel = metadata['channel']
        user = authorized(session, slack_user, channel)
        language = config['channels'][channel]
        actions = payload.get('actions', [])
        if actions:
            action = actions[0]
            value = json.loads(action.get('value', '{}'))
            event_id = int(value['event_id'])
            if not evidence_for_event(session, event_id):
                raise ValueError('source_policy_restricted')
            if action['action_id'] == 'dismiss':
                return {'modal': True, 'event_id': event_id, 'channel': channel,
                        'trigger_id': payload['trigger_id'], 'language': language}
            key = digest(json.dumps([slack_user, channel, action.get('action_ts'), action['action_id'], event_id]))
            decide(session, user.id, event_id, action['action_id'], key=key)
            return {'decided': True}
        if payload.get('type') == 'view_submission':
            metadata = json.loads(payload['view']['private_metadata'])
            if not evidence_for_event(session, metadata['event_id']):
                raise ValueError('source_policy_restricted')
            reason = payload['view']['state']['values']['reason']['reason']['value']
            decide(session, user.id, metadata['event_id'], 'dismiss', reason, key=payload['view']['id'])
            return {'decided': True}
        if not text:
            text = 'help'
        query = {'query': text[:2000], 'channel': channel, 'slack_user': slack_user,
                 'language': language, 'thread_ts': event.get('thread_ts') or event.get('ts')}
        identifier = payload.get('event_id') or payload.get('trigger_id')
        if not identifier:
            raise ValueError('slack_event_id_required')
        user_id = user.id
    enqueue(db, 'slack_query', query, 'slack:' + identifier, user_id)
    return {'queued': True}


def open_reason_modal(client, data):
    es = data['language'] == 'es'
    client.views_open(trigger_id=data['trigger_id'], view={
        'type': 'modal', 'callback_id': 'radar_dismiss',
        'private_metadata': json.dumps({'channel': data['channel'], 'event_id': data['event_id']}),
        'title': {'type': 'plain_text', 'text': 'Descartar señal' if es else 'Dismiss signal'},
        'submit': {'type': 'plain_text', 'text': 'Confirmar' if es else 'Confirm'},
        'blocks': [{'type': 'input', 'block_id': 'reason', 'label': {'type': 'plain_text', 'text': 'Motivo' if es else 'Reason'},
                    'element': {'type': 'plain_text_input', 'action_id': 'reason', 'multiline': True, 'max_length': 2000}}]})


def socket_client(db, vault):
    from slack_sdk.socket_mode import SocketModeClient
    from slack_sdk.socket_mode.response import SocketModeResponse
    with db.session() as session:
        token = vault.get(session, 'slack_app')
    web = client_for(db, vault)
    test_connection(db, vault)
    client = SocketModeClient(app_token=token, web_client=web)

    def receive(socket, request):
        # ACK never waits on a model or remote source.
        socket.send_socket_mode_response(SocketModeResponse(envelope_id=request.envelope_id))
        payload = request.payload
        try:
            result = accept_payload(db, payload)
            if result and result.get('modal'):
                open_reason_modal(web, result)
            elif result and not payload.get('event') and payload.get('type') != 'view_submission':
                channel = payload.get('channel_id') or payload.get('channel', {}).get('id')
                user = payload.get('user_id') or payload.get('user', {}).get('id')
                web.chat_postEphemeral(channel=channel, user=user, text='Agenda Radar: OK')
        except Exception:
            # Do not echo payloads, secrets or evidence into error logs.
            with db.session() as session:
                session.merge(State(key='slack_last_error', value={'at': time.time(), 'code': 'interaction_rejected'}))
    client.socket_mode_request_listeners.append(receive)
    return client


def message_blocks(item, settings):
    es = item.get('language') == 'es'
    title = html.escape(item.get('title', 'Agenda Radar'))[:250]
    summary = html.escape(item.get('summary') or item.get('reason', ''))[:1800]
    sources = '\n'.join('<' + quote(doc['url'], safe=':/?=&%#') + '|' + html.escape(doc['title'])[:150] + '>' for doc in item.get('evidence', [])[:5])
    blocks: list[dict[str, Any]] = [{'type': 'section', 'text': {'type': 'mrkdwn', 'text': f'*{title}*\n{summary}'}}]
    if sources:
        blocks.append({'type': 'section', 'text': {'type': 'mrkdwn', 'text': sources[:2800]}})
    if item.get('event_id'):
        labels = [('follow', 'Seguir' if es else 'Follow'), ('dismiss', 'Descartar' if es else 'Dismiss'),
                  ('mute', 'Silenciar 2 h' if es else 'Mute 2h'), ('claim', 'Me encargo' if es else 'I’ll review')]
        buttons: list[dict[str, Any]] = [{'type': 'button', 'text': {'type': 'plain_text', 'text': label}, 'action_id': action,
                    'value': json.dumps({'event_id': item['event_id']})} for action, label in labels]
        buttons.append({'type': 'button', 'text': {'type': 'plain_text', 'text': 'Ver fuentes' if es else 'View sources'},
                        'url': settings.app_base_url.rstrip('/')+f"/events/{item['event_id']}"})
        blocks.append({'type': 'actions', 'elements': buttons})
    return blocks


def deliver_telegram_agent(db, vault, settings):
    """Deliver queued agent cards targeted to Telegram to linked enabled editors."""
    import asyncio

    from .alerts import quiet
    from .editorial import active_config
    from .models import TelegramLink
    from .telegram_bot import Telegram

    with db.session() as session:
        _, config = active_config(session)
        if not config.telegram_enabled or not vault.get(session, 'telegram'):
            return
        delivery = session.scalar(
            select(ChannelDelivery)
            .where(
                ChannelDelivery.channel == 'telegram',
                ChannelDelivery.status == 'pending',
                ChannelDelivery.run_after <= time.time(),
            )
            .order_by(ChannelDelivery.id)
            .limit(1)
        )
        if not delivery:
            return
        if quiet(config, settings.app_timezone):
            delivery.run_after = time.time() + 300
            return
        follow = session.get(EditorialFollowup, delivery.event_id) if delivery.event_id else None
        if delivery.expires_at < time.time() or (follow and follow.status in ('dismissed', 'completed')):
            delivery.status = 'expired'
            return
        if follow and follow.muted_until > time.time():
            delivery.run_after = follow.muted_until
            return
        payload = dict(delivery.payload)
        evidence = payload.get('evidence', [])
        if evidence and len(permitted_evidence(session, evidence, 'external')) != len(evidence):
            delivery.status = 'policy_restricted'
            return
        if any(
            item.get('hash')
            and (not (document := session.get(Document, item['id'])) or document.content_hash != item['hash'])
            for item in evidence
        ):
            delivery.status = 'superseded'
            return
        chats = [
            link.chat_id
            for link in session.scalars(
                select(TelegramLink)
                .join(User)
                .where(TelegramLink.chat_id.is_not(None), User.enabled.is_(True))
            )
            if link.chat_id and link.muted_until <= time.time()
        ]
        if not chats:
            delivery.status = 'expired'
            return
        delivery.status, delivery.attempt = 'sending', delivery.attempt + 1
        identifier = delivery.id
        event_id = delivery.event_id
    es = payload.get('language') == 'es'
    title = payload.get('title', 'Agenda Radar')
    summary = payload.get('summary') or payload.get('reason', '')
    links = '\n'.join(doc['url'] for doc in evidence[:3])
    text_msg = f"{title}\n{summary}\n{links}"
    if event_id:
        text_msg += f"\n{settings.app_base_url.rstrip('/')}/events/{event_id}"
    reply_markup = (
        {
            'inline_keyboard': [
                [
                    {'text': 'Seguir' if es else 'Follow', 'callback_data': f'follow:{event_id}'},
                    {'text': 'Descartar' if es else 'Dismiss', 'callback_data': f'dismiss:{event_id}'},
                ]
            ]
        }
        if event_id
        else None
    )
    tg = Telegram(db, vault)
    try:
        async def _send_all():
            for chat_id in chats:
                body: dict[str, Any] = {'chat_id': chat_id, 'text': text_msg[:4000]}
                if reply_markup:
                    body['reply_markup'] = reply_markup
                await tg.call('sendMessage', body)

        asyncio.run(_send_all())
        with db.session() as session:
            current = session.get(ChannelDelivery, identifier)
            current.status = 'sent'
    except Exception:
        with db.session() as session:
            current = session.get(ChannelDelivery, identifier)
            current.status = 'pending' if current.attempt < 5 else 'failed'
            current.error_code = 'telegram_delivery_failed'
            current.run_after = time.time() + min(3600, 60 * current.attempt)


def deliver_one(db, vault, settings):
    deliver_telegram_agent(db, vault, settings)
    with db.session() as session:
        config = slack_config(session)
        if not config.get('enabled'):
            return
        local_hour = datetime.now(ZoneInfo(config.get('timezone', settings.app_timezone))).hour
        start, end = config.get('quiet_start', 23), config.get('quiet_end', 7)
        quiet = start <= local_hour < end if start < end else (local_hour >= start or local_hour < end) if start != end else False
        delivery = session.scalar(select(ChannelDelivery).where(ChannelDelivery.channel == 'slack', ChannelDelivery.status == 'pending', ChannelDelivery.run_after <= time.time()).order_by(ChannelDelivery.id).limit(1))
        if not delivery:
            return
        if not delivery.payload.get('user_id'):
            sent = session.scalar(select(func.count()).select_from(ChannelDelivery).where(
                ChannelDelivery.destination == delivery.destination, ChannelDelivery.status == 'sent',
                ChannelDelivery.created_at >= time.time()-3600))
            if quiet or sent >= config.get('max_per_hour', 6):
                delivery.run_after = time.time()+300
                return
        follow = session.get(EditorialFollowup, delivery.event_id) if delivery.event_id else None
        if delivery.expires_at < time.time() or delivery.destination not in config['channels'] or (follow and follow.status in ('dismissed', 'completed')):
            delivery.status = 'expired'
            return
        if follow and follow.muted_until > time.time():
            delivery.run_after = follow.muted_until
            return
        payload = dict(delivery.payload)
        evidence = payload.get('evidence', [])
        eligible = permitted_evidence(session, evidence, 'external')
        # Revoke the entire generated message if any supporting source has become private.
        if evidence and len(eligible) != len(evidence):
            delivery.status = 'policy_restricted'
            return
        if any(item.get('hash') and (not (document := session.get(Document, item['id'])) or document.content_hash != item['hash']) for item in evidence):
            delivery.status = 'superseded'
            return
        if payload.get('user_id'):
            try:
                if authorized(session, payload['slack_user'], delivery.destination).id != payload['user_id']:
                    raise ValueError('slack_identity_changed')
            except ValueError:
                delivery.status = 'revoked'
                return
        thread = session.scalar(select(SlackThread).where(SlackThread.event_id == delivery.event_id, SlackThread.channel_id == delivery.destination)) if delivery.event_id else None
        thread_ts = payload.get('thread_ts') or (thread.thread_ts if thread else None)
        delivery.status, delivery.attempt = 'sending', delivery.attempt+1
        identifier, destination = delivery.id, delivery.destination
    web = client_for(db, vault)
    try:
        response = web.chat_postMessage(channel=destination, text=payload.get('title', 'Agenda Radar'),
            blocks=message_blocks(payload, settings), thread_ts=thread_ts,
            client_msg_id=str(__import__('uuid').uuid5(__import__('uuid').NAMESPACE_URL, delivery.dedupe_key)),
            unfurl_links=False, unfurl_media=False)
        with db.session() as session:
            current = session.get(ChannelDelivery, identifier)
            current.status, current.remote_id = 'sent', response['ts']
            if current.event_id and not thread:
                session.execute(insert(SlackThread).values(channel_id=destination, event_id=current.event_id,
                    thread_ts=response['ts'], url=f"https://app.slack.com/client/{config['team_id']}/{destination}/thread/{destination}-{response['ts']}").on_conflict_do_nothing())
    except Exception as exc:
        response = getattr(exc, 'response', None)
        code = response.get('error', 'delivery_failed') if response is not None else 'delivery_unknown'
        with db.session() as session:
            current = session.get(ChannelDelivery, identifier)
            # Unknown transport outcomes need review, not a blind duplicate post.
            current.status = 'pending' if code in ('ratelimited', 'internal_error', 'service_unavailable') and current.attempt < 5 else 'failed'
            current.error_code = code
            retry = int(response.headers.get('Retry-After', '60')) if response is not None and code == 'ratelimited' else 60
            current.run_after = time.time()+max(30, min(3600, retry))


def answer_slack(db, vault, settings, job):
    import re

    from .assistant import answer_query
    data = job.payload
    with db.session() as session:
        authorized(session, data['slack_user'], data['channel'])
    query = re.sub(r'<@[A-Z0-9]+>', '', data['query']).strip()
    es = data['language'] == 'es'
    answer: dict[str, Any]
    if query.lower() in ('help', 'ayuda'):
        answer = {'answer': '/radar agenda · /radar brechas · /radar briefing · @Agenda Radar + pregunta' if es else '/radar agenda · /radar gaps · /radar briefing · @Agenda Radar + question', 'evidence': []}
    elif query.lower() in ('agenda', 'brechas', 'gaps', 'briefing'):
        from .scoring import compare
        with db.session() as session:
            rows = compare(session, '24h')['rows']
            if query.lower() in ('brechas', 'gaps'):
                rows = [r for r in rows if r['gap_pp'] is not None and r['gap_pp'] > 0]
                rows.sort(key=lambda r: r['gap_pp'], reverse=True)
            evidence: list[dict[str, Any]] = []
            lines: list[str] = []
            for row in rows:
                ev = evidence_for_event(session, row['event_id'])[:1]
                if not ev:
                    continue
                evidence.extend(ev)
                ref = f"{row['reference_share']:.1f}%" if row['reference_share'] is not None else '—'
                gap = f"{row['gap_pp']:+.1f} pp" if row['gap_pp'] is not None else '—'
                lines.append(
                    f"• {row['label']} (Ref {ref} · {'Brecha' if es else 'Gap'} {gap} · {row['independent_source_count']} {'grupos' if es else 'groups'})"
                )
                if len(evidence) >= 5:
                    break
        summary_text = (
            '\n'.join(lines)
            if lines
            else ('Sin evidencia autorizada para compartir.' if es else 'No authorized evidence available to share.')
        )
        answer = {'answer': summary_text, 'evidence': evidence}
    else:
        answer = answer_query(db, vault, query, language=data['language'], destination='external')
    payload = {'title': 'Agenda Radar', 'summary': answer['answer'], 'evidence': answer['evidence'],
               'language': data['language'], 'thread_ts': data.get('thread_ts'), 'user_id': job.user_id,
               'slack_user': data['slack_user']}
    with db.session() as session:
        authorized(session, data['slack_user'], data['channel'])
        session.execute(insert(ChannelDelivery).values(dedupe_key=f'query:{job.id}', destination=data['channel'],
            payload=payload, expires_at=time.time()+3600).on_conflict_do_nothing())
    return {'queued_delivery': True}
