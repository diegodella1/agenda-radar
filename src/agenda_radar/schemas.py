from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Role = Literal["reader", "analyst", "editor", "media_admin", "superadmin"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceInput(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["rss", "web", "google_news", "google_trends", "manual", "x"] = "rss"
    channel: Literal["web", "x", "search", "video"] = "web"
    url: str = Field(max_length=2048)
    scope: Literal["own", "reference", "public"] = "reference"
    group_name: str = Field(min_length=1, max_length=200)
    weight: float = Field(default=100, ge=0, le=100)
    poll_interval: int = Field(default=600, ge=300, le=86400)
    country: str = Field(default="AR", max_length=10)
    legal_basis: str = Field(min_length=5, max_length=2000)
    enabled: bool = True
    options: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def separate_channels(self):
        if self.kind == "google_trends":
            self.scope, self.channel = "public", "search"
        elif self.kind == "x":
            self.scope, self.channel = "public", "x"
        return self

    @field_validator("url")
    @classmethod
    def valid_url(cls, value):
        parsed = urlsplit(value)
        if (
            parsed.scheme not in ("https", "http")
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ValueError("Usar URL HTTP(S) pública sin credenciales")
        return value


class EditorialConfig(StrictModel):
    topic_keywords: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "economía": ["inflación", "dólar", "economía", "presupuesto"],
            "política": ["congreso", "gobierno", "elecciones", "senado"],
            "local": ["municipio", "vecinos", "barrio"],
        }
    )
    topic_priorities: dict[str, float] = Field(default_factory=dict)
    entity_priorities: dict[str, float] = Field(default_factory=dict)
    geo_priorities: dict[str, float] = Field(default_factory=dict)
    hourly_priorities: dict[str, float] = Field(default_factory=dict)
    timezone: str = "America/Argentina/Buenos_Aires"
    source_weights: dict[str, float] = Field(default_factory=dict)
    excluded_terms: list[str] = Field(default_factory=list)
    review_terms: list[str] = Field(default_factory=list)
    editorial_tone: str = Field(default="Claro, sobrio, español argentino.", max_length=4000)
    enabled_alert_rules: list[
        Literal[
            "editorial_gap",
            "emerging_event",
            "priority_without_coverage",
            "agenda_shift",
            "high_impact_update",
            "source_health_failure",
        ]
    ] = [
        "editorial_gap",
        "emerging_event",
        "priority_without_coverage",
        "agenda_shift",
        "high_impact_update",
        "source_health_failure",
    ]
    agenda_shift_pp: float = Field(default=15, ge=1, le=100)
    high_impact_new_documents: int = Field(default=3, ge=2, le=100)
    emerging_velocity: float = Field(default=1, ge=0, le=100)
    priority_threshold: float = Field(default=0.75, ge=0, le=1)
    minimum_gap_pp: float = Field(default=15, ge=0, le=100)
    minimum_independent_sources: int = Field(default=3, ge=2, le=50)
    minimum_confidence: float = Field(default=0.7, ge=0, le=1)
    cooldown_minutes: int = Field(default=90, ge=20, le=10080)
    rearm_change_pp: float = Field(default=10, ge=0, le=100)
    quiet_start: int = Field(default=23, ge=0, le=23)
    quiet_end: int = Field(default=7, ge=0, le=23)
    run_enabled: bool = True
    ai_enabled: bool = False
    telegram_enabled: bool = False
    manual_coverage_complete_until: float | None = None
    ai_model: str = ""
    extraction_enabled: bool = False
    extraction_model: str = ""
    extraction_input_usd_million: float = Field(default=0, ge=0)
    extraction_output_usd_million: float = Field(default=0, ge=0)
    ai_input_usd_million: float = Field(default=0, ge=0)
    ai_output_usd_million: float = Field(default=0, ge=0)
    daily_budget_usd: float = Field(default=1, ge=0, le=10000)
    monthly_budget_usd: float = Field(default=20, ge=0, le=100000)

    @field_validator("topic_priorities", "entity_priorities", "geo_priorities", "hourly_priorities")
    @classmethod
    def priorities(cls, value):
        if any(not 0 <= number <= 5 for number in value.values()):
            raise ValueError("Multiplicadores entre 0 y 5")
        return value

    @field_validator("timezone")
    @classmethod
    def timezone_valid(cls, value):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Zona horaria inválida") from exc
        return value

    @field_validator("source_weights")
    @classmethod
    def weights(cls, value):
        if any(not 0 <= number <= 100 for number in value.values()):
            raise ValueError("Pesos entre 0 y 100")
        return value


class DocumentInput(StrictModel):
    url: str
    title: str = Field(min_length=1, max_length=2000)
    excerpt: str = Field(default="", max_length=4000)
    external_id: str = ""
    published_at: float | None = None
    publisher: str | None = None
    signal_value: str | None = Field(default=None, max_length=100)

    @field_validator("url")
    @classmethod
    def valid_url(cls, value):
        return SourceInput.valid_url(value)


class DecisionInput(StrictModel):
    event_id: int
    action: Literal["follow", "dismiss", "review", "accept"]
    reason: str = Field(default="", max_length=4000)


class UserInput(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=256)
    role: Role = "editor"


class QueryInput(StrictModel):
    query: str = Field(min_length=1, max_length=2000)
    window: Literal["1h", "6h", "24h", "72h", "7d"] = "24h"
    purpose: Literal[
        "answer_telegram", "explain_score", "disambiguate", "format_recommendation", "daily_brief"
    ] = "answer_telegram"


class Answer(StrictModel):
    answer: str
    citation_document_ids: list[int]
    confidence: Literal["low", "medium", "high"]
    limitations: list[str]
    suggested_action: str | None
