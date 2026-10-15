import time
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(30), default="reader")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[float] = mapped_column(default=time.time)


class LoginSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    csrf: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[float] = mapped_column(index=True)


class Audit(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100))
    object_kind: Mapped[str] = mapped_column(String(40))
    object_id: Mapped[str] = mapped_column(String(100), default="")
    before: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    after: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    at: Mapped[float] = mapped_column(default=time.time, index=True)


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30), default="rss")
    channel: Mapped[str] = mapped_column(String(30), default="web")
    url: Mapped[str] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(String(20), default="reference")
    group_name: Mapped[str] = mapped_column(String(200))
    weight: Mapped[float] = mapped_column(default=100)
    country: Mapped[str] = mapped_column(String(10), default="AR")
    legal_basis: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True)
    poll_interval: Mapped[int] = mapped_column(default=600)
    last_success: Mapped[float | None] = mapped_column()
    next_poll: Mapped[float] = mapped_column(default=0, index=True)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    error_code: Mapped[str | None] = mapped_column(String(80))
    etag: Mapped[str | None] = mapped_column(Text)
    modified: Mapped[str | None] = mapped_column(Text)
    options: Mapped[dict] = mapped_column(JSON, default=dict)


class IngestRun(Base):
    __tablename__ = "ingest_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    started_at: Mapped[float] = mapped_column(default=time.time)
    ended_at: Mapped[float | None] = mapped_column()
    status: Mapped[str] = mapped_column(default="running")
    count: Mapped[int] = mapped_column(default=0)
    error_code: Mapped[str | None] = mapped_column()


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("publisher", "canonical_url"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    publisher: Mapped[str] = mapped_column(String(200))
    group_name: Mapped[str] = mapped_column(String(200))
    canonical_url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    excerpt: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(64))
    published_at: Mapped[float | None] = mapped_column(index=True)
    observed_at: Mapped[float] = mapped_column(default=time.time, index=True)
    ingested_at: Mapped[float] = mapped_column(default=time.time)
    channel: Mapped[str] = mapped_column(default="web")
    topic: Mapped[str] = mapped_column(default="general")
    entities: Mapped[list] = mapped_column(JSON, default=list)


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (UniqueConstraint("source_id", "external_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    external_id: Mapped[str] = mapped_column(Text)
    observed_at: Mapped[float] = mapped_column(default=time.time)


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    title: Mapped[str] = mapped_column(Text)
    excerpt: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    observed_at: Mapped[float] = mapped_column(default=time.time)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(Text)
    topic: Mapped[str] = mapped_column(default="general")
    status: Mapped[str] = mapped_column(default="active")
    first_observed_at: Mapped[float] = mapped_column(default=time.time)
    confidence: Mapped[float] = mapped_column(default=0.6)
    parent_event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"))


class Mention(Base):
    __tablename__ = "event_mentions"
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    similarity: Mapped[float] = mapped_column(default=1)
    human_verified: Mapped[bool] = mapped_column(default=False)
    method: Mapped[str] = mapped_column(default="heuristic")


class OwnCoverage(Base):
    __tablename__ = "own_coverage"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    url: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(default="web")
    published_at: Mapped[float] = mapped_column()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column()
    reason: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[float] = mapped_column(default=time.time)


class ConfigVersion(Base):
    __tablename__ = "config_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    at: Mapped[float] = mapped_column(default=time.time)
    reason: Mapped[str] = mapped_column(Text, default="Inicial")


class State(Base):
    __tablename__ = "state"
    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class ScoreSnapshot(Base):
    __tablename__ = "score_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    window: Mapped[str] = mapped_column()
    as_of: Mapped[float] = mapped_column(index=True)
    config_version: Mapped[int] = mapped_column(ForeignKey("config_versions.id"))
    algorithm_version: Mapped[str] = mapped_column(default="salience-0.1")
    payload: Mapped[dict] = mapped_column(JSON)


class TrendSample(Base):
    __tablename__ = "trend_samples"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    label: Mapped[str] = mapped_column(Text)
    geo: Mapped[str] = mapped_column(default="AR")
    value: Mapped[str | None] = mapped_column()
    unit: Mapped[str] = mapped_column(default="search_trend_active")
    captured_at: Mapped[float] = mapped_column(default=time.time, index=True)
    source_url: Mapped[str] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("source_id", "label", "captured_at"),)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_status_run_after", "status", "run_after"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column()
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(default="pending")
    attempt: Mapped[int] = mapped_column(default=0)
    run_after: Mapped[float] = mapped_column(default=time.time)
    lease_until: Mapped[float] = mapped_column(default=0)
    owner: Mapped[str | None] = mapped_column()
    idempotency_key: Mapped[str] = mapped_column(unique=True)
    error_code: Mapped[str | None] = mapped_column()
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    rule: Mapped[str] = mapped_column(default="editorial_gap")
    dedupe_key: Mapped[str] = mapped_column(unique=True)
    status: Mapped[str] = mapped_column(default="open")
    at: Mapped[float] = mapped_column(default=time.time, index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("alert_id", "user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(default="pending")
    attempt: Mapped[int] = mapped_column(default=0)
    run_after: Mapped[float] = mapped_column(default=time.time)
    expires_at: Mapped[float] = mapped_column()
    sent_at: Mapped[float | None] = mapped_column()
    error_code: Mapped[str | None] = mapped_column()


class TelegramLink(Base):
    __tablename__ = "telegram_links"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    chat_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    code_hash: Mapped[str | None] = mapped_column(unique=True)
    expires_at: Mapped[float] = mapped_column(default=0)
    muted_until: Mapped[float] = mapped_column(default=0)


class Secret(Base):
    __tablename__ = "secrets"
    name: Mapped[str] = mapped_column(primary_key=True)
    encrypted: Mapped[str] = mapped_column(Text)


class Prompt(Base):
    __tablename__ = "prompts"
    id: Mapped[int] = mapped_column(primary_key=True)
    purpose: Mapped[str] = mapped_column()
    template: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column()
    status: Mapped[str] = mapped_column(default="draft")
    test_result: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[float] = mapped_column(default=time.time)


class APIUsage(Base):
    __tablename__ = "api_usage"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[float] = mapped_column(default=time.time, index=True)
    operation: Mapped[str] = mapped_column()
    model: Mapped[str] = mapped_column()
    status: Mapped[str] = mapped_column(default="reserved")
    reserved_usd: Mapped[float] = mapped_column()
    cost_usd: Mapped[float] = mapped_column(default=0)
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
