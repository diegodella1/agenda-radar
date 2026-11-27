"""Authenticated configuration and editorial APIs for collaboration."""
import secrets
import time
from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from .agents import build_preview, decide, slack_config
from .collaboration_models import (
    AgentRun,
    AIProfile,
    AIRun,
    ChannelDelivery,
    EditorialAgent,
    EditorialFollowup,
    SlackIdentity,
    SlackThread,
)
from .jobs import enqueue
from .models import Decision, Event, Source, State
from .security import ROLES, audit, digest


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=120)
    provider: Literal['openai', 'anthropic', 'compatible']
    model: str = Field(min_length=1, max_length=160)
    base_url: str = Field(default='', max_length=500)
    network: Literal['internal', 'external'] = 'external'
    ca_file: str = Field(default='', max_length=500)
    enabled: bool = False
    timeout_seconds: int = Field(default=45, ge=5, le=120)
    max_output_tokens: int = Field(default=1500, ge=100, le=4000)
    daily_requests: int = Field(default=100, ge=1, le=10000)
    daily_tokens: int = Field(default=200000, ge=1000, le=10000000)
    input_rate: float | None = Field(default=None, ge=0, le=1000)
    output_rate: float | None = Field(default=None, ge=0, le=1000)
    credential: str | None = Field(default=None, max_length=4000)

    @model_validator(mode='after')
    def valid_destination(self):
        if self.provider == 'compatible':
            url = urlsplit(self.base_url)
            if self.network != 'internal' or url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
                raise ValueError('An internal model requires a valid internal endpoint.')
        elif self.network != 'external' or self.base_url:
            raise ValueError('Cloud providers use their fixed external endpoints.')
        return self


class AgentInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=120)
    kind: Literal['vigilance', 'briefing', 'followup']
    enabled: bool = False
    language: Literal['en', 'es'] = 'en'
    timezone: str = 'America/Argentina/Buenos_Aires'
    hour: int = Field(default=8, ge=0, le=23)
    window: Literal['1h', '6h', '24h', '72h', '7d'] = '24h'
    topics: list[str] = Field(default_factory=list, max_length=50)
    source_ids: list[int] = Field(default_factory=list, max_length=100)
    channel_id: str = Field(default='', pattern=r'^([CG][A-Z0-9]+|telegram|web)?$')
    profile_id: int | None = None
    max_items: int = Field(default=5, ge=1, le=10)

    @model_validator(mode='after')
    def valid_timezone(self):
        try:
            ZoneInfo(self.timezone)
        except Exception as exc:
            raise ValueError('Invalid timezone') from exc
        return self


class SlackInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool = False
    team_id: str = Field(default='', pattern=r'^(T[A-Z0-9]+)?$')
    channels: dict[str, Literal['en', 'es']] = Field(default_factory=dict, max_length=20)
    quiet_start: int = Field(default=23, ge=0, le=23)
    quiet_end: int = Field(default=7, ge=0, le=23)
    max_per_hour: int = Field(default=6, ge=1, le=20)
    timezone: str = 'America/Argentina/Buenos_Aires'
    bot_token: str | None = Field(default=None, max_length=4000)
    app_token: str | None = Field(default=None, max_length=4000)


class FollowInput(BaseModel):
    action: Literal['follow', 'dismiss', 'claim', 'mute', 'complete', 'useful', 'noise']
    reason: str = Field(default='', max_length=2000)


def record(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def install(app, db, vault, settings, require, render):
    @app.get('/collaboration')
    def page(request: Request, user=Depends(require('editor'))):
        return render(request, 'collaboration.html', title='Agentes y colaboración')

    @app.get('/api/v1/admin/ai-profiles')
    def profiles(user=Depends(require('superadmin'))):
        with db.session() as session:
            return [record(row) for row in session.scalars(select(AIProfile))]

    def save_profile(payload, user, identifier=None):
        with db.session() as session:
            profile = session.get(AIProfile, identifier) if identifier else AIProfile()
            if not profile:
                raise HTTPException(404)
            data = payload.model_dump(exclude={'credential'})
            changed = not identifier or payload.credential is not None or any(getattr(profile, key) != value for key, value in data.items() if key != 'enabled')
            if payload.enabled and (changed or not profile.tested_at):
                raise ValueError('Test the saved profile before enabling it.')
            for key, value in data.items():
                setattr(profile, key, value)
            if changed:
                profile.tested_at = None
            session.add(profile)
            session.flush()
            if payload.credential is not None:
                vault.set(session, f'ai:{profile.id}', payload.credential)
            audit(session, user.id, 'configure', 'ai_profile', profile.id)
            return record(profile)

    @app.post('/api/v1/admin/ai-profiles')
    def create_profile(payload: ProfileInput, user=Depends(require('superadmin'))):
        return save_profile(payload, user)

    @app.put('/api/v1/admin/ai-profiles/{identifier}')
    def update_profile(identifier: int, payload: ProfileInput, user=Depends(require('superadmin'))):
        return save_profile(payload, user, identifier)

    @app.post('/api/v1/admin/ai-profiles/{identifier}/test')
    def test_profile(identifier: int, user=Depends(require('superadmin'))):
        with db.session() as session:
            if not session.get(AIProfile, identifier):
                raise HTTPException(404)
        return {'job_id': enqueue(db, 'model_test', {'profile_id': identifier}, secrets.token_hex(16), user.id)}

    @app.get('/api/v1/admin/ai-routing')
    def routing(user=Depends(require('superadmin'))):
        with db.session() as session:
            row = session.get(State, 'ai_routes')
            return row.value if row else {}

    @app.put('/api/v1/admin/ai-routing')
    def set_routing(payload: dict[str, int | None], user=Depends(require('superadmin'))):
        if set(payload) - {'answer_telegram', 'extract_event', 'daily_brief', 'explain_score', 'disambiguate', 'format_recommendation'}:
            raise ValueError('Unknown AI task')
        with db.session() as session:
            for identifier in payload.values():
                if identifier and not session.get(AIProfile, identifier):
                    raise ValueError('Unknown AI profile')
            session.merge(State(key='ai_routes', value=payload))
            audit(session, user.id, 'configure', 'ai_routes')
        return {'ok': True}

    @app.get('/api/v1/admin/slack')
    def get_slack(user=Depends(require('superadmin'))):
        with db.session() as session:
            return {**slack_config(session), 'bot_configured': bool(vault.get(session, 'slack_bot')),
                    'app_configured': bool(vault.get(session, 'slack_app'))}

    @app.put('/api/v1/admin/slack')
    def configure_slack(payload: SlackInput, user=Depends(require('superadmin'))):
        import re
        if any(not re.fullmatch(r'[CG][A-Z0-9]+', channel) for channel in payload.channels):
            raise ValueError('Invalid channel ID')
        try:
            ZoneInfo(payload.timezone)
        except Exception as exc:
            raise ValueError('Invalid timezone') from exc
        with db.session() as session:
            for field, key in ((payload.bot_token, 'slack_bot'), (payload.app_token, 'slack_app')):
                if field is not None:
                    vault.set(session, key, field)
            if payload.enabled and (not payload.team_id or not payload.channels or not vault.get(session, 'slack_bot') or not vault.get(session, 'slack_app')):
                raise ValueError('Configure workspace, channels and both Slack tokens first.')
            session.merge(State(key='slack_config', value=payload.model_dump(exclude={'bot_token', 'app_token'})))
            audit(session, user.id, 'configure', 'slack')
        return {'ok': True}

    @app.post('/api/v1/admin/slack/test')
    def test_slack(user=Depends(require('superadmin'))):
        return {'job_id': enqueue(db, 'slack_test', {}, secrets.token_hex(16), user.id)}

    @app.post('/api/v1/slack/pair')
    def pair(user=Depends(require('editor'))):
        code = secrets.token_urlsafe(24)
        with db.session() as session:
            link = session.get(SlackIdentity, user.id) or SlackIdentity(user_id=user.id)
            link.code_hash, link.expires_at = digest(code), time.time()+600
            session.add(link)
        return {'code': code, 'expires_in': 600}

    @app.get('/api/v1/admin/agents')
    def list_agents(user=Depends(require('media_admin'))):
        with db.session() as session:
            return [record(row) for row in session.scalars(select(EditorialAgent))]

    def save_agent(payload, user, identifier=None):
        with db.session() as session:
            if payload.profile_id and not session.get(AIProfile, payload.profile_id):
                raise ValueError('Unknown AI profile')
            if any(not session.get(Source, source_id) for source_id in payload.source_ids):
                raise ValueError('Unknown source')
            config = slack_config(session)
            from .editorial import active_config
            _, ed_config = active_config(session)
            if payload.enabled:
                if payload.channel_id == 'web':
                    pass
                elif payload.channel_id == 'telegram':
                    if not ed_config.telegram_enabled:
                        raise ValueError('Enable Telegram in Editorial criteria first.')
                elif not config.get('enabled') or payload.channel_id not in config.get('channels', {}):
                    raise ValueError('Configure and enable an authorized Slack channel, Telegram or Web destination first.')
            agent = session.get(EditorialAgent, identifier) if identifier else EditorialAgent()
            if not agent:
                raise HTTPException(404)
            for key, value in payload.model_dump().items():
                setattr(agent, key, value)
            session.add(agent)
            session.flush()
            audit(session, user.id, 'configure', 'agent', agent.id)
            return record(agent)

    @app.post('/api/v1/admin/agents')
    def create_agent(payload: AgentInput, user=Depends(require('media_admin'))):
        return save_agent(payload, user)

    @app.put('/api/v1/admin/agents/{identifier}')
    def update_agent(identifier: int, payload: AgentInput, user=Depends(require('media_admin'))):
        return save_agent(payload, user, identifier)

    @app.post('/api/v1/admin/agents/{identifier}/preview')
    def preview(identifier: int, user=Depends(require('media_admin'))):
        return build_preview(db, identifier)

    @app.post('/api/v1/admin/agents/{identifier}/preview-ai')
    def preview_ai(identifier: int, user=Depends(require('media_admin'))):
        build_preview(db, identifier)
        return {'job_id': enqueue(db, 'agent_preview', {'agent_id': identifier}, secrets.token_hex(16), user.id)}

    @app.put('/api/v1/admin/sources/{identifier}/data-policy')
    def policy(identifier: int, payload: dict[str, Literal['internal', 'external']], user=Depends(require('media_admin'))):
        if set(payload) != {'policy'}:
            raise ValueError('A source policy is required')
        with db.session() as session:
            source = session.get(Source, identifier)
            if not source:
                raise HTTPException(404)
            source.options = {**source.options, 'data_policy': payload['policy']}
            audit(session, user.id, 'data_policy', 'source', identifier, after=payload)
        return {'ok': True}

    @app.get('/api/v1/editorial/followups')
    def followups(user=Depends(require('editor'))):
        from .models import User
        with db.session() as session:
            users = {u.id: u.email for u in session.scalars(select(User))}
            return [
                {
                    **record(row),
                    'title': (ev.label if (ev := session.get(Event, row.event_id)) else f'#{row.event_id}'),
                    'owner_email': users.get(row.owner_id) if row.owner_id else None,
                    'threads': [record(thread) for thread in session.scalars(select(SlackThread).where(SlackThread.event_id == row.event_id))],
                }
                for row in session.scalars(select(EditorialFollowup).order_by(EditorialFollowup.updated_at.desc()).limit(100))
            ]

    @app.get('/api/v1/editorial/recent-events')
    def recent_events(user=Depends(require('editor'))):
        with db.session() as session:
            return [
                {'id': e.id, 'label': e.label, 'topic': e.topic}
                for e in session.scalars(select(Event).where(Event.status == 'active').order_by(Event.id.desc()).limit(60))
            ]

    @app.post('/api/v1/editorial/followups/{event_id}')
    def action(event_id: int, payload: FollowInput, user=Depends(require('editor'))):
        with db.session() as session:
            decide(session, user.id, event_id, payload.action, payload.reason)
        return {'ok': True}

    @app.get('/api/v1/admin/collaboration-status')
    def status(user=Depends(require('media_admin'))):
        with db.session() as session:
            pulse = session.get(State, 'collaboration_heartbeat')
            result = {'heartbeat': pulse.value if pulse else None,
                      'runs': [record(row) for row in session.scalars(select(AgentRun).order_by(AgentRun.id.desc()).limit(30))],
                      'deliveries': [record(row) for row in session.scalars(select(ChannelDelivery).order_by(ChannelDelivery.id.desc()).limit(50))],
                      'feedback': [record(row) for row in session.scalars(select(Decision).where(Decision.action.in_(['useful', 'noise', 'claim', 'complete'])).order_by(Decision.id.desc()).limit(100))]}
            if ROLES[user.role] >= ROLES['superadmin']:
                result['ai_runs'] = [record(row) for row in session.scalars(select(AIRun).order_by(AIRun.id.desc()).limit(50))]
            return result
