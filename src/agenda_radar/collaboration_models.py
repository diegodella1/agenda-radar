"""Additive persistence for provider-independent editorial collaboration."""
import time

from sqlalchemy import JSON, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class AIProfile(Base):
    __tablename__ = 'ai_profiles'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    provider: Mapped[str] = mapped_column()
    model: Mapped[str] = mapped_column()
    base_url: Mapped[str] = mapped_column(default='')
    network: Mapped[str] = mapped_column(default='external')
    ca_file: Mapped[str] = mapped_column(default='')
    enabled: Mapped[bool] = mapped_column(default=False)
    timeout_seconds: Mapped[int] = mapped_column(default=45)
    max_output_tokens: Mapped[int] = mapped_column(default=1500)
    daily_requests: Mapped[int] = mapped_column(default=100)
    daily_tokens: Mapped[int] = mapped_column(default=200000)
    input_rate: Mapped[float | None] = mapped_column()
    output_rate: Mapped[float | None] = mapped_column()
    tested_at: Mapped[float | None] = mapped_column()


class AIRun(Base):
    __tablename__ = 'ai_runs'
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey('ai_profiles.id'))
    provider: Mapped[str] = mapped_column()
    model: Mapped[str] = mapped_column()
    operation: Mapped[str] = mapped_column()
    at: Mapped[float] = mapped_column(default=time.time)
    status: Mapped[str] = mapped_column(default='running')
    duration_ms: Mapped[int] = mapped_column(default=0)
    reserved_tokens: Mapped[int] = mapped_column(default=0)
    reserved_usd: Mapped[float | None] = mapped_column()
    input_tokens: Mapped[int | None] = mapped_column()
    output_tokens: Mapped[int | None] = mapped_column()
    cost_usd: Mapped[float | None] = mapped_column()


class EditorialAgent(Base):
    __tablename__ = 'editorial_agents'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    kind: Mapped[str] = mapped_column()
    enabled: Mapped[bool] = mapped_column(default=False)
    language: Mapped[str] = mapped_column(default='en')
    timezone: Mapped[str] = mapped_column(default='America/Argentina/Buenos_Aires')
    hour: Mapped[int] = mapped_column(default=8)
    window: Mapped[str] = mapped_column(default='24h')
    topics: Mapped[list] = mapped_column(JSON, default=list)
    source_ids: Mapped[list] = mapped_column(JSON, default=list)
    channel_id: Mapped[str] = mapped_column(default='')
    profile_id: Mapped[int | None] = mapped_column(ForeignKey('ai_profiles.id'))
    max_items: Mapped[int] = mapped_column(default=5)
    next_run: Mapped[float] = mapped_column(default=0)
    state: Mapped[dict] = mapped_column(JSON, default=dict)


class AgentRun(Base):
    __tablename__ = 'agent_runs'
    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey('editorial_agents.id'))
    at: Mapped[float] = mapped_column(default=time.time)
    preview: Mapped[bool] = mapped_column(default=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(default='completed')


class SlackIdentity(Base):
    __tablename__ = 'slack_identities'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    slack_user_id: Mapped[str | None] = mapped_column(unique=True)
    code_hash: Mapped[str | None] = mapped_column()
    expires_at: Mapped[float] = mapped_column(default=0)


class EditorialFollowup(Base):
    __tablename__ = 'editorial_followups'
    event_id: Mapped[int] = mapped_column(ForeignKey('events.id'), primary_key=True)
    status: Mapped[str] = mapped_column(default='following')
    owner_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    muted_until: Mapped[float] = mapped_column(default=0)
    updated_at: Mapped[float] = mapped_column(default=time.time)


class ChannelDelivery(Base):
    __tablename__ = 'channel_deliveries'
    id: Mapped[int] = mapped_column(primary_key=True)
    dedupe_key: Mapped[str] = mapped_column(unique=True)
    channel: Mapped[str] = mapped_column(default='slack')
    destination: Mapped[str] = mapped_column()
    event_id: Mapped[int | None] = mapped_column(ForeignKey('events.id'))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(default='pending')
    attempt: Mapped[int] = mapped_column(default=0)
    run_after: Mapped[float] = mapped_column(default=time.time)
    expires_at: Mapped[float] = mapped_column()
    remote_id: Mapped[str | None] = mapped_column()
    error_code: Mapped[str | None] = mapped_column()
    created_at: Mapped[float] = mapped_column(default=time.time)


class SlackThread(Base):
    __tablename__ = 'slack_threads'
    __table_args__ = (UniqueConstraint('channel_id', 'event_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[str] = mapped_column()
    event_id: Mapped[int] = mapped_column(ForeignKey('events.id'))
    thread_ts: Mapped[str] = mapped_column()
    url: Mapped[str] = mapped_column(Text, default='')
