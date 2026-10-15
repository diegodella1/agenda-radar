import csv
import io
import json
import re
import secrets
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from .config import Settings
from .db import Database
from .editorial import active_config, publish_config
from .events import merge_events, split_event
from .ingest import store_document
from .jobs import enqueue
from .models import (
    Alert,
    APIUsage,
    Audit,
    ConfigVersion,
    Decision,
    Document,
    Event,
    Job,
    LoginSession,
    Mention,
    OwnCoverage,
    Prompt,
    Secret,
    Source,
    State,
    TrendSample,
    User,
)
from .presentation import editorial_view
from .schemas import (
    DecisionInput,
    DocumentInput,
    EditorialConfig,
    QueryInput,
    SourceInput,
    UserInput,
)
from .scoring import WINDOWS, compare, source_healthy
from .security import (
    ROLES,
    Vault,
    audit,
    create_user,
    digest,
    hash_password,
    pairing_code,
    verify_password,
)

ROOT = Path(__file__).parent
ASSET_VERSION = digest("".join((ROOT / "static" / name).read_text() for name in ("app.js", "app.css", "public.css")))[:12]


def row_dict(row, exclude=()):
    return {
        column.name: getattr(row, column.name)
        for column in row.__table__.columns
        if column.name not in exclude
    }


class LoginInput(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)


class PasswordInput(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class SetupInput(LoginInput):
    code: str = Field(min_length=20, max_length=100)


class ConfigInput(BaseModel):
    config: EditorialConfig
    reason: str = Field(min_length=3, max_length=1000)


class CoverageInput(BaseModel):
    event_id: int
    url: str
    published_at: float
    channel: str = "web"


class SplitInput(BaseModel):
    document_ids: list[int] = Field(min_length=1, max_length=500)
    label: str = Field(min_length=3, max_length=2000)


class MergeInput(BaseModel):
    other_event_id: int


class SecretInput(BaseModel):
    name: str
    value: str = Field(min_length=5, max_length=2000)


class PromptInput(BaseModel):
    purpose: str = "answer_telegram"
    template: str = Field(min_length=10, max_length=10000)
    model: str = Field(min_length=1, max_length=100)


def create_app(settings: Settings | None = None):
    settings = settings or Settings()
    db, vault = Database(settings.database_path), Vault(settings.secrets_dir)
    base_path = "/demo" if settings.demo_mode else ""
    session_cookie = "radar_demo_session" if settings.demo_mode else "radar_session"
    app = FastAPI(
        title="Agenda Radar", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None
    )
    app.state.db, app.state.settings, app.state.vault = db, settings, vault
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    templates = Jinja2Templates(directory=ROOT / "templates")
    templates.env.globals.update(base_path=base_path, demo=settings.demo_mode, demo_enabled=settings.demo_enabled, asset_version=ASSET_VERSION)
    templates.env.filters["date"] = lambda value: (
        datetime.fromtimestamp(value, ZoneInfo(settings.app_timezone)).strftime("%d/%m %H:%M")
        if value
        else "Sin registro"
    )
    templates.env.filters["pct"] = lambda value: f"{value:.1f}" if value is not None else "—"

    def require(role="reader"):
        def dependency(request: Request):
            user = getattr(request.state, "user", None)
            if user is None:
                raise HTTPException(401, "Iniciar sesión")
            if ROLES[user.role] < ROLES[role]:
                with db.session() as session:
                    audit(session, user.id, "access_denied", "route", request.url.path)
                raise HTTPException(403, "Tu rol no permite esta acción")
            return user

        return dependency

    @app.middleware("http")
    async def security_middleware(request, call_next):
        if (
            settings.cookie_secure
            and settings.app_base_url.startswith("https://")
            and request.url.scheme != "https"
            and not request.url.path.startswith("/health/")
        ):
            target = settings.app_base_url.rstrip("/") + request.url.path
            if request.url.query:
                target += "?" + request.url.query
            return RedirectResponse(target, status_code=307)
        request.state.user, request.state.csrf = None, ""
        demo_dispatch = settings.demo_enabled and (request.url.path == "/demo" or request.url.path.startswith("/demo/"))
        token = None if demo_dispatch else request.cookies.get(session_cookie)
        if settings.demo_mode and request.url.path == "/api/v1/auth/login":
            token = None
        if (
            request.headers.get("content-length", "0").isdigit()
            and int(request.headers.get("content-length", "0")) > 300000
        ):
            return JSONResponse({"detail": "Solicitud demasiado grande"}, status_code=413)
        if token:
            with db.session() as session:
                login = session.get(LoginSession, digest(token))
                if login and login.expires_at > time.time():
                    user = session.get(User, login.user_id)
                    if user and user.enabled:
                        request.state.user, request.state.csrf = user, login.csrf
        if not demo_dispatch and request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.headers.get("x-requested-with") != "AgendaRadar":
                return JSONResponse({"detail": "Solicitud inválida (CSRF)"}, status_code=403)
            if request.state.user and not secrets.compare_digest(
                request.headers.get("x-csrf-token", ""), request.state.csrf
            ):
                return JSONResponse({"detail": "Sesión o CSRF inválido"}, status_code=403)
            origin = request.headers.get("origin")
            if origin and origin != str(request.base_url).rstrip("/"):
                return JSONResponse({"detail": "Origen no permitido"}, status_code=403)
        if settings.demo_mode:
            path = request.url.path
            permitted = (
                path in {"/", "/login", "/compare", "/events", "/trends", "/alerts", "/history",
                         "/assistant", "/integrations", "/admin/sources", "/admin/config",
                         "/api/v1/auth/login", "/api/v1/auth/logout", "/api/v1/auth/me",
                         "/api/v1/agendas/compare", "/api/v1/events", "/api/v1/alerts",
                         "/api/v1/trends", "/api/v1/assistant/query", "/api/v1/export/agenda.md",
                         "/api/v1/editorial/decisions", "/api/v1/editorial/coverage"}
                or path.startswith(("/static/", "/events/", "/evidence/", "/api/v1/events/",
                                    "/api/v1/jobs/", "/api/v1/demo/"))
                or re.fullmatch(r"/api/v1/admin/sources(?:/(?:test|export\.csv|[0-9]+(?:/poll)?))?", path)
                or re.fullmatch(r"/api/v1/admin/config(?:/(?:preview|publish|[0-9]+/rollback))?", path)
            )
            if not permitted:
                return JSONResponse({"detail": "Esta función no está habilitada en la demo."}, 403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if settings.cookie_secure and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if not request.url.path.startswith("/static"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ValueError)
    async def bad_value(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(
            {
                "detail": [
                    {"field": ".".join(str(x) for x in e["loc"]), "message": e["msg"]}
                    for e in exc.errors()
                ]
            },
            status_code=422,
        )

    @app.get("/health/live")
    def live():
        return {"status": "alive"}

    @app.get("/health/ready")
    def ready():
        try:
            with db.session() as session:
                revision = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
                pulse = session.get(State, "worker_heartbeat")
                healthy = bool(revision and pulse and time.time() - pulse.value["at"] < 120)
            return JSONResponse(
                {"status": "ready" if healthy else "degraded"}, status_code=200 if healthy else 503
            )
        except Exception:
            return JSONResponse({"status": "uninitialized"}, status_code=503)

    @app.get("/account", response_class=HTMLResponse)
    def account_page(request: Request, user=Depends(require())):
        return render(request, "account.html", title="Mi cuenta")

    @app.post("/api/v1/auth/password")
    def change_password(payload: PasswordInput, user=Depends(require())):
        with db.session() as session:
            stored = session.get(User, user.id)
            if not verify_password(payload.current_password, stored.password_hash):
                raise HTTPException(403, "Contraseña actual incorrecta")
            stored.password_hash = hash_password(payload.new_password)
            for login in session.scalars(
                select(LoginSession).where(LoginSession.user_id == user.id)
            ):
                session.delete(login)
            audit(session, user.id, "password_changed", "user", user.id)
        return {"status": "changed"}

    @app.get("/setup", response_class=HTMLResponse)
    def setup_page(request: Request):
        with db.session() as session:
            if session.scalar(select(User.id).limit(1)):
                return RedirectResponse(base_path + "/login", status_code=303)
        return templates.TemplateResponse(request=request, name="setup.html", context={})

    @app.post("/api/v1/auth/setup")
    def setup(payload: SetupInput):
        from .bootstrap import enroll

        enroll(db, payload.code, payload.email, payload.password)
        (settings.secrets_dir / "setup-code").unlink(missing_ok=True)
        return {"status": "created"}

    @app.post("/api/v1/auth/login")
    def login(payload: LoginInput, request: Request):
        if settings.demo_enabled and payload.email == "demo" and payload.password == "demo":
            return {"redirect": "/demo/login"}
        now = time.time()
        limiter_key = "login:" + digest(
            (request.client.host if request.client else "local") + ":" + payload.email.lower()
        )
        with db.session() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            limiter = session.get(State, limiter_key)
            if (
                limiter
                and limiter.value.get("until", 0) > now
                and limiter.value.get("count", 0) >= 8
            ):
                raise HTTPException(429, "Demasiados intentos. Esperar 15 minutos.")
            count = limiter.value["count"] if limiter and limiter.value.get("until", 0) > now else 0
            session.merge(State(key=limiter_key, value={"count": count + 1, "until": now + 900}))
            user = session.scalar(select(User).where(User.email == payload.email.lower()))
            valid = bool(
                user and user.enabled and verify_password(payload.password, user.password_hash)
            )
            if valid:
                session.merge(State(key=limiter_key, value={"count": 0, "until": 0}))
                token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
                session.add(
                    LoginSession(
                        token_hash=digest(token),
                        user_id=user.id,
                        csrf=csrf,
                        expires_at=now + settings.session_hours * 3600,
                    )
                )
                audit(session, user.id, "login", "session")
        if not valid:
            raise HTTPException(401, "Credenciales inválidas")
        response = JSONResponse({"csrf": csrf, "role": user.role})
        response.set_cookie(
            session_cookie,
            token,
            path=base_path or "/",
            httponly=True,
            secure=settings.cookie_secure,
            samesite="strict",
            max_age=settings.session_hours * 3600,
        )
        return response

    @app.post("/api/v1/auth/logout")
    def logout(request: Request, user=Depends(require())):
        with db.session() as session:
            login = session.get(LoginSession, digest(request.cookies[session_cookie]))
            session.delete(login)
        response = JSONResponse({"ok": True})
        response.delete_cookie(session_cookie, path=base_path or "/")
        return response

    @app.get("/api/v1/auth/me")
    def me(request: Request, user=Depends(require())):
        return {"id": user.id, "email": user.email, "role": user.role, "csrf": request.state.csrf}

    @app.get("/api/v1/openapi.json")
    def schema(user=Depends(require())):
        return app.openapi()

    @app.get("/api/v1/agendas/compare")
    def agendas(
        window: str = "24h",
        topic: str = "",
        source: str = "",
        channel: str = "",
        geo: str = "",
        user=Depends(require()),
    ):
        if window not in WINDOWS:
            raise HTTPException(422, "Ventana inválida")
        with db.session() as session:
            return editorial_view(
                session,
                window,
                now=settings.demo_epoch,
                topic=topic,
                source=source,
                channel=channel,
                geo=geo,
            )

    @app.get("/api/v1/events")
    def events(
        window="24h",
        sort="priority",
        topic: str | None = None,
        source: int | None = None,
        channel: str | None = None,
        geo: str | None = None,
        page: int = Query(1, ge=1),
        user=Depends(require()),
    ):
        if window not in WINDOWS or sort not in ("priority", "gap", "reference_share"):
            raise HTTPException(422, "Filtro inválido")
        with db.session() as session:
            result = compare(session, window, now=settings.demo_epoch)
        rows = [
            row
            for row in result["rows"]
            if (not topic or row["topic"] == topic)
            and (not source or source in row["source_ids"])
            and (not channel or channel in row["channels"])
            and (not geo or geo in row["geographies"])
        ]
        key = "gap_pp" if sort == "gap" else sort
        rows.sort(key=lambda row: row[key] if row[key] is not None else -1, reverse=True)
        result["total"], result["rows"] = len(rows), rows[(page - 1) * 30 : page * 30]
        return result

    def event_data(session, event_id):
        event = session.get(Event, event_id)
        if not event:
            raise HTTPException(404, "Acontecimiento inexistente")
        documents = list(
            session.scalars(
                select(Document)
                .join(Mention)
                .where(Mention.event_id == event_id)
                .order_by(Document.observed_at)
            )
        )
        return {
            **row_dict(event),
            "documents": [row_dict(doc) for doc in documents],
            "decisions": [
                row_dict(d)
                for d in session.scalars(select(Decision).where(Decision.event_id == event_id))
            ],
        }

    @app.get("/api/v1/events/{event_id}")
    def event_api(event_id: int, user=Depends(require())):
        with db.session() as session:
            return event_data(session, event_id)

    @app.post("/api/v1/events/{event_id}/merge")
    def merge(event_id: int, payload: MergeInput, user=Depends(require("editor"))):
        with db.session() as session:
            merge_events(session, event_id, payload.other_event_id, user.id)
        return {"ok": True}

    @app.post("/api/v1/events/{event_id}/split")
    def split(event_id: int, payload: SplitInput, user=Depends(require("editor"))):
        with db.session() as session:
            return {
                "event_id": split_event(
                    session, event_id, payload.document_ids, payload.label, user.id
                )
            }

    @app.post("/api/v1/editorial/decisions")
    def decision(payload: DecisionInput, user=Depends(require("editor"))):
        with db.session() as session:
            if not session.get(Event, payload.event_id):
                raise HTTPException(404, "Acontecimiento inexistente")
            session.add(Decision(**payload.model_dump(), user_id=user.id))
            audit(
                session,
                user.id,
                payload.action,
                "event",
                payload.event_id,
                after={"reason": payload.reason},
            )
        return {"ok": True}

    @app.post("/api/v1/editorial/coverage")
    def coverage(payload: CoverageInput, user=Depends(require("editor"))):
        from .ingest import canonical_url

        if payload.published_at > time.time() + 300 or payload.published_at <= 0:
            raise ValueError("Fecha de publicación inválida")
        if settings.demo_mode and settings.demo_epoch is not None:
            payload = payload.model_copy(update={"published_at": min(payload.published_at, settings.demo_epoch)})
        with db.session() as session:
            if not session.get(Event, payload.event_id):
                raise HTTPException(404, "Acontecimiento inexistente")
            session.add(
                OwnCoverage(
                    **{**payload.model_dump(), "url": canonical_url(payload.url)}, user_id=user.id
                )
            )
            audit(
                session, user.id, "coverage", "event", payload.event_id, after=payload.model_dump()
            )
        return {"ok": True}

    @app.get("/api/v1/admin/sources")
    def list_sources(user=Depends(require("media_admin"))):
        with db.session() as session:
            return [row_dict(s) for s in session.scalars(select(Source).order_by(Source.id))]

    @app.post("/api/v1/admin/sources")
    def add_source(payload: SourceInput, user=Depends(require("media_admin"))):
        with db.session() as session:
            if settings.demo_mode and len(list(session.scalars(select(Source.id)))) >= 30:
                raise HTTPException(429, "Máximo de 30 fuentes en la demo")
            source = Source(**payload.model_dump())
            session.add(source)
            session.flush()
            audit(session, user.id, "create", "source", source.id, after=payload.model_dump())
            return {"id": source.id}

    @app.patch("/api/v1/admin/sources/{source_id}")
    def edit_source(source_id: int, payload: SourceInput, user=Depends(require("media_admin"))):
        with db.session() as session:
            source = session.get(Source, source_id)
            if not source:
                raise HTTPException(404, "Fuente inexistente")
            before = row_dict(source)
            for key, value in payload.model_dump().items():
                setattr(source, key, value)
            source.etag, source.modified, source.next_poll = None, None, 0
            audit(
                session,
                user.id,
                "edit",
                "source",
                source.id,
                before=before,
                after=payload.model_dump(),
            )
        return {"ok": True}

    @app.get("/api/v1/admin/sources/export.csv")
    def export_sources(user=Depends(require("media_admin"))):
        fields = [
            "name",
            "kind",
            "channel",
            "url",
            "scope",
            "group_name",
            "weight",
            "poll_interval",
            "country",
            "legal_basis",
            "enabled",
        ]
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        with db.session() as session:
            for source in session.scalars(select(Source)):
                writer.writerow({key: getattr(source, key) for key in fields})
        return PlainTextResponse(
            output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="fuentes.csv"'},
        )

    @app.post("/api/v1/admin/sources/import")
    async def import_sources(request: Request, user=Depends(require("media_admin"))):
        content = (await request.json()).get("csv", "")
        if len(content) > 200000:
            raise ValueError("CSV demasiado grande")
        parsed = [SourceInput.model_validate(row) for row in csv.DictReader(io.StringIO(content))]
        if len(parsed) > 100:
            raise ValueError("Máximo 100 fuentes por importación")
        with db.session() as session:
            for payload in parsed:
                if not session.scalar(select(Source.id).where(Source.url == payload.url)):
                    session.add(Source(**payload.model_dump()))
            audit(session, user.id, "csv_import", "source", after={"count": len(parsed)})
        return {"count": len(parsed)}

    @app.post("/api/v1/admin/sources/test")
    def test_source(payload: SourceInput, user=Depends(require("media_admin"))):
        if settings.demo_mode:
            return demo_job({"mode": "simulated", "message": "Prueba simulada: no se consultó la URL.",
                             "source": payload.name}, user.id)
        return {
            "job_id": enqueue(
                db, "test_source", payload.model_dump(), secrets.token_hex(16), user.id
            )
        }

    @app.post("/api/v1/admin/sources/{source_id}/poll")
    def force_poll(source_id: int, user=Depends(require("media_admin"))):
        if settings.demo_mode:
            with db.session() as session:
                if not session.get(Source, source_id):
                    raise HTTPException(404, "Fuente inexistente")
            return demo_job({"mode": "simulated", "message": "Sin conexión externa. Usá Simular novedades para incorporar el lote de ejemplo."}, user.id)
        with db.session() as session:
            if not session.get(Source, source_id):
                raise HTTPException(404, "Fuente inexistente")
        return {
            "job_id": enqueue(
                db,
                "poll",
                {"source_id": source_id},
                f"manual-poll:{source_id}:{int(time.time() // 60)}",
                user.id,
            )
        }

    @app.post("/api/v1/admin/sources/{source_id}/documents")
    def import_document(
        source_id: int, payload: DocumentInput, user=Depends(require("media_admin"))
    ):
        with db.session() as session:
            source = session.get(Source, source_id)
            if not source:
                raise HTTPException(404, "Fuente inexistente")
            document = store_document(session, source, payload)
            audit(session, user.id, "manual_import", "document", document.id)
            return {"id": document.id}

    @app.get("/api/v1/admin/config")
    def config_get(user=Depends(require("media_admin"))):
        with db.session() as session:
            version, config = active_config(session)
            return {
                "version": version,
                "config": config.model_dump(),
                "versions": [
                    row_dict(v)
                    for v in session.scalars(
                        select(ConfigVersion).order_by(ConfigVersion.id.desc()).limit(50)
                    )
                ],
            }

    def check_global_config(session, new, user):
        _, old = active_config(session)
        keys = (
            "ai_enabled",
            "extraction_enabled",
            "extraction_model",
            "extraction_input_usd_million",
            "extraction_output_usd_million",
            "telegram_enabled",
            "ai_model",
            "ai_input_usd_million",
            "ai_output_usd_million",
            "daily_budget_usd",
            "monthly_budget_usd",
            "run_enabled",
        )
        if user.role != "superadmin" and any(
            getattr(new, key) != getattr(old, key) for key in keys
        ):
            raise HTTPException(403, "Solo superadmin cambia proveedores y límites globales")

    @app.post("/api/v1/admin/config/preview")
    def preview(payload: ConfigInput, user=Depends(require("media_admin"))):
        with db.session() as session:
            check_global_config(session, payload.config, user)
            fingerprint = digest(payload.config.model_dump_json())
            version, _ = active_config(session)
            session.merge(
                State(
                    key=f"preview:{user.id}",
                    value={"hash": fingerprint, "version": version, "at": time.time()},
                )
            )
            return {"before": compare(session, now=settings.demo_epoch), "after": compare(session, config=payload.config, now=settings.demo_epoch)}

    @app.post("/api/v1/admin/config/publish")
    def publish(payload: ConfigInput, user=Depends(require("media_admin"))):
        with db.session() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            check_global_config(session, payload.config, user)
            preview = session.get(State, f"preview:{user.id}")
            current, _ = active_config(session)
            if (
                not preview
                or preview.value["hash"] != digest(payload.config.model_dump_json())
                or preview.value["version"] != current
                or time.time() - preview.value["at"] > 1800
            ):
                raise HTTPException(409, "Previsualizar esta configuración antes de publicar")
            return {"version": publish_config(session, payload.config, user.id, payload.reason)}

    @app.post("/api/v1/admin/config/{version_id}/rollback")
    def rollback(version_id: int, user=Depends(require("media_admin"))):
        with db.session() as session:
            version = session.get(ConfigVersion, version_id)
            if not version:
                raise HTTPException(404, "Versión inexistente")
            config = EditorialConfig.model_validate(version.payload)
            check_global_config(session, config, user)
            return {
                "version": publish_config(
                    session, config, user.id, f"Restaurar versión {version_id}"
                )
            }

    @app.get("/api/v1/admin/providers")
    def providers(user=Depends(require("superadmin"))):
        with db.session() as session:
            names = set(session.scalars(select(Secret.name)))
            return {
                name: "configured" if name in names else "no_credentials"
                for name in ("openai", "telegram", "x")
            }

    @app.post("/api/v1/admin/providers")
    def set_provider(payload: SecretInput, user=Depends(require("superadmin"))):
        with db.session() as session:
            vault.set(session, payload.name, payload.value)
            audit(session, user.id, "rotate_secret", "provider", payload.name)
        return {"ok": True}

    @app.post("/api/v1/admin/users")
    def add_user(payload: UserInput, user=Depends(require("media_admin"))):
        if ROLES[payload.role] >= ROLES[user.role] and user.role != "superadmin":
            raise HTTPException(403, "No podés otorgar ese rol")
        with db.session() as session:
            created = create_user(session, payload.email, payload.password, payload.role)
            audit(session, user.id, "create", "user", created.id, after={"role": created.role})
            return {"id": created.id}

    @app.post("/api/v1/admin/users/{user_id}/disable")
    def disable_user(user_id: int, user=Depends(require("media_admin"))):
        with db.session() as session:
            target = session.get(User, user_id)
            if not target or user_id == user.id or ROLES[target.role] >= ROLES[user.role]:
                raise HTTPException(403, "No podés desactivar esta cuenta")
            target.enabled = False
            audit(session, user.id, "disable", "user", target.id)
        return {"ok": True}

    @app.post("/api/v1/telegram/pair")
    def pair(user=Depends(require())):
        with db.session() as session:
            return {"command": "/start " + pairing_code(session, user.id), "expires_in": 600}

    @app.get("/api/v1/alerts")
    def alerts(user=Depends(require())):
        with db.session() as session:
            return [
                row_dict(a)
                for a in session.scalars(select(Alert).order_by(Alert.at.desc()).limit(100))
            ]

    @app.post("/api/v1/alerts/{alert_id}/ack")
    def acknowledge(alert_id: int, user=Depends(require("editor"))):
        with db.session() as session:
            alert = session.get(Alert, alert_id)
            if not alert:
                raise HTTPException(404, "Alerta inexistente")
            alert.status = "acknowledged"
            audit(session, user.id, "ack", "alert", alert_id)
        return {"ok": True}

    @app.post("/api/v1/assistant/query")
    def ask(payload: QueryInput, user=Depends(require("editor"))):
        if settings.demo_mode:
            from .assistant import fallback, retrieve
            with db.session() as session:
                evidence = retrieve(session, payload.query, window=payload.window, now=settings.demo_epoch)
            return demo_job(fallback(evidence, "Respuesta de demostración, sin llamada a OpenAI"), user.id)
        return {
            "job_id": enqueue(db, "query", payload.model_dump(), secrets.token_hex(16), user.id)
        }

    @app.get("/api/v1/jobs/{job_id}")
    def job_status(job_id: int, user=Depends(require())):
        with db.session() as session:
            job = session.get(Job, job_id)
            if not job or (job.user_id != user.id and user.role != "superadmin"):
                raise HTTPException(404, "Trabajo inexistente")
            return row_dict(job)

    @app.post("/api/v1/admin/jobs/{job_id}/retry")
    def retry_job(job_id: int, user=Depends(require("superadmin"))):
        with db.session() as session:
            job = session.get(Job, job_id)
            if not job or job.status != "failed":
                raise ValueError("Solo trabajos fallidos pueden reintentarse")
            job.status, job.run_after, job.attempt = "pending", time.time(), 0
            audit(session, user.id, "retry", "job", job.id)
        return {"ok": True}

    @app.get("/api/v1/trends")
    def trends(user=Depends(require())):
        with db.session() as session:
            x_sources = list(session.scalars(select(Source).where(Source.kind == "x")))
            x_status = (
                "sampled"
                if any(source_healthy(source, time.time()) for source in x_sources)
                else "unavailable"
            )
            return {
                "x": x_status,
                "x_caveat": "Muestra de cuentas/listas configuradas, hasta 100 publicaciones por consulta. No mide tendencias globales.",
                "samples": [
                    row_dict(s)
                    for s in session.scalars(
                        select(TrendSample).order_by(TrendSample.captured_at.desc()).limit(100)
                    )
                ],
            }

    @app.post("/api/v1/admin/trends/import")
    async def import_trends(request: Request, user=Depends(require("media_admin"))):
        payload = await request.json()
        content = payload.get("csv", "")
        if len(content) > 200000:
            raise ValueError("CSV demasiado grande")
        with db.session() as session:
            source = session.get(Source, int(payload["source_id"]))
            if not source or source.kind != "google_trends":
                raise ValueError("Seleccionar fuente Google Trends")
            count = 0
            for row in csv.DictReader(io.StringIO(content)):
                label = row.get("Trends") or row.get("Tendencias") or row.get("label")
                if not label:
                    raise ValueError("CSV requiere columna Trends, Tendencias o label")
                session.add(
                    TrendSample(
                        source_id=source.id,
                        label=label[:2000],
                        geo=source.country,
                        value=row.get("Search volume") or row.get("Volumen de búsquedas"),
                        unit="manual_csv_search_trend",
                        source_url=source.url,
                    )
                )
                count += 1
            audit(session, user.id, "csv_import", "trends", source.id, after={"count": count})
        return {"count": count}

    @app.post("/api/v1/admin/prompts")
    def create_prompt(payload: PromptInput, user=Depends(require("superadmin"))):
        with db.session() as session:
            prompt = Prompt(**payload.model_dump())
            session.add(prompt)
            session.flush()
            audit(session, user.id, "create", "prompt", prompt.id)
            return {"id": prompt.id}

    @app.post("/api/v1/admin/prompts/{prompt_id}/test")
    def test_prompt(prompt_id: int, user=Depends(require("superadmin"))):
        with db.session() as session:
            if not session.get(Prompt, prompt_id):
                raise HTTPException(404, "Prompt inexistente")
        return {
            "job_id": enqueue(
                db, "test_prompt", {"prompt_id": prompt_id}, secrets.token_hex(16), user.id
            )
        }

    @app.post("/api/v1/admin/prompts/{prompt_id}/publish")
    def publish_prompt(prompt_id: int, user=Depends(require("superadmin"))):
        with db.session() as session:
            prompt = session.get(Prompt, prompt_id)
            if not prompt or not prompt.test_result.get("passed"):
                raise ValueError("El prompt necesita una prueba IA aprobada")
            for old in session.scalars(
                select(Prompt).where(Prompt.purpose == prompt.purpose, Prompt.status == "published")
            ):
                old.status = "retired"
            prompt.status = "published"
            audit(session, user.id, "publish", "prompt", prompt.id)
        return {"ok": True}

    @app.post("/api/v1/admin/backups")
    def backup(user=Depends(require("superadmin"))):
        return {"job_id": enqueue(db, "backup", {}, secrets.token_hex(16), user.id)}

    @app.get("/api/v1/admin/backups/{filename}")
    def download_backup(filename: str, user=Depends(require("superadmin"))):
        if not re.fullmatch(r"agenda-[0-9]{19}\.db", filename):
            raise HTTPException(404, "Backup no encontrado")
        path = settings.backup_dir / filename
        if not path.is_file() or path.is_symlink():
            raise HTTPException(404, "Backup no encontrado")
        with db.session() as session:
            audit(session, user.id, "backup_download", "backup", filename)
        return FileResponse(path, media_type="application/octet-stream", filename=filename)

    @app.get("/api/v1/admin/health")
    def admin_health(user=Depends(require("superadmin"))):
        with db.session() as session:
            pulse = session.get(State, "worker_heartbeat")
            return {
                "worker": pulse.value if pulse else None,
                "incidents": [
                    s.value
                    for s in session.scalars(
                        select(State).where(State.key.like("source_incident:%"))
                    )
                ],
                "sources": [row_dict(s) for s in session.scalars(select(Source))],
                "jobs": [
                    row_dict(j)
                    for j in session.scalars(select(Job).order_by(Job.id.desc()).limit(100))
                ],
            }

    @app.get("/api/v1/admin/readiness")
    def readiness(user=Depends(require("superadmin"))):
        from .readiness import report

        return report(db, settings)

    @app.get("/api/v1/export/agenda.md")
    def export(window="24h", user=Depends(require("analyst"))):
        if window not in WINDOWS:
            raise ValueError("Ventana inválida")
        with db.session() as session:
            result = compare(session, window, now=settings.demo_epoch)
        lines = ["# Agenda Radar", f"Ventana: {window}", result["sample_caveat"], ""]
        for row in result["rows"]:
            lines += [
                "## " + row["label"].replace("\n", " "),
                f"Brecha: {row['gap_pp']} pp. Grupos independientes: {row['independent_source_count']}.",
            ]
            lines += [
                f"- {d['title'].replace(chr(10), ' ')} — {d['url']}" for d in row["documents"]
            ]
        return PlainTextResponse(
            "\n\n".join(lines),
            media_type="text/markdown",
            headers={"Content-Disposition": 'attachment; filename="agenda.md"'},
        )

    def render(request, template, **context):
        if not request.state.user:
            return RedirectResponse(base_path + "/login", status_code=303)
        return templates.TemplateResponse(
            request=request,
            name=template,
            context={
                "user": request.state.user,
                "csrf": request.state.csrf,
                "roles": ROLES,
                "now": settings.demo_epoch or time.time(),
                **context,
            },
        )

    def public_page(request, page="home"):
        pages = {
            "home": ("Una agenda. Más perspectiva.", "Compará tu cobertura con medios de referencia, detectá brechas y decidí con evidencia."),
            "about": ("Acerca de Agenda Radar", "Una herramienta para ampliar la mirada editorial sin delegar el criterio periodístico."),
            "funcionalidades": ("Cómo funciona", "Fuentes, acontecimientos, agenda comparada y alertas en una misma mesa editorial."),
            "casos-de-uso": ("Casos de uso", "Del pase de redacción al seguimiento de una noticia: decisiones editoriales con contexto."),
            "roadmap": ("Alcance y próximos pasos", "Qué incluye el MVP de Agenda Radar y qué queda por validar o evaluar."),
        }
        title, description = pages[page]
        return templates.TemplateResponse(
            request=request, name="public.html",
            context={"page": page, "title": title, "description": description,
                     "public_url": settings.app_base_url.rstrip("/") + ("/home" if page == "home" else "/" + page)},
        )

    @app.get("/home", response_class=HTMLResponse)
    @app.get("/about", response_class=HTMLResponse)
    @app.get("/funcionalidades", response_class=HTMLResponse)
    @app.get("/casos-de-uso", response_class=HTMLResponse)
    @app.get("/roadmap", response_class=HTMLResponse)
    def marketing_page(request: Request):
        return public_page(request, request.url.path.strip("/"))

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request):
        return templates.TemplateResponse(request=request, name="login.html", context={"csrf": ""})

    @app.get("/", response_class=HTMLResponse)
    @app.get("/compare", response_class=HTMLResponse)
    @app.get("/events", response_class=HTMLResponse)
    def dashboard(request: Request, window="24h", topic="", source="", channel="", geo=""):
        if request.url.path == "/" and not request.state.user and not settings.demo_mode:
            return public_page(request)
        if window not in WINDOWS:
            window = "24h"
        with db.session() as session:
            data = editorial_view(
                session,
                window,
                now=settings.demo_epoch,
                topic=topic,
                source=source,
                channel=channel,
                geo=geo,
            )
            source_list = data["sources"]
        return render(
            request,
            "dashboard.html",
            data=data,
            sources=source_list,
            title="Agenda comparada" if request.url.path == "/compare" else "Radar editorial",
        )

    @app.get("/events/{event_id}", response_class=HTMLResponse)
    def event_page(
        request: Request,
        event_id: int,
        window="24h",
        topic="",
        source="",
        channel="",
        geo="",
        evidence_source: int | None = None,
    ):
        if window not in WINDOWS:
            window = "24h"
        with db.session() as session:
            data = event_data(session, event_id)
            data["suggestions"] = [
                state.value
                for state in session.scalars(select(State).where(State.key.like("event_review:%")))
                if state.value.get("event_id") == event_id
            ]
            comparison = editorial_view(session, window, now=settings.demo_epoch)
            context = editorial_view(
                session,
                window,
                now=settings.demo_epoch,
                topic=topic,
                source=source,
                channel=channel,
                geo=geo,
            )
            score = next((r for r in comparison["rows"] if r["event_id"] == event_id), None)
        # Keep historical evidence available, but distinguish the selected scoring window.
        visible_ids = {d["id"] for d in score["documents"]} if score else set()
        data["evidence_source"] = next(
            (s["name"] for s in comparison["sources"] if s["id"] == evidence_source), None
        )
        if evidence_source is not None:
            visible_ids = (
                {d["id"] for d in score["documents"] if evidence_source in d["source_ids"]}
                if score
                else set()
            )
        data["current_documents"] = sorted(
            [d for d in data["documents"] if d["id"] in visible_ids],
            key=lambda d: d["published_at"] or d["observed_at"],
        )
        data["past_documents"] = [d for d in data["documents"] if d["id"] not in visible_ids]
        return render(
            request, "event.html", event=data, score=score, data=context, title="Acontecimiento"
        )

    @app.get("/assistant", response_class=HTMLResponse)
    def assistant_page(request: Request, user=Depends(require("editor"))):
        return render(request, "assistant.html", title="Consultar evidencia")

    @app.get("/trends", response_class=HTMLResponse)
    @app.get("/alerts", response_class=HTMLResponse)
    @app.get("/history", response_class=HTMLResponse)
    def records_page(request: Request, user=Depends(require())):
        with db.session() as session:
            path = request.url.path
            model = TrendSample if path == "/trends" else Alert if path == "/alerts" else Decision
            rows = [
                row_dict(x)
                for x in session.scalars(
                    select(model).order_by(model.__table__.c.id.desc()).limit(100)
                )
            ]
            x_sources = list(session.scalars(select(Source).where(Source.kind == "x")))
            x_documents = (
                list(
                    session.scalars(
                        select(Document)
                        .where(Document.channel == "x")
                        .order_by(Document.observed_at.desc())
                        .limit(30)
                    )
                )
                if path == "/trends"
                else []
            )
        return render(
            request,
            "records.html",
            x_sources=x_sources,
            x_documents=x_documents,
            rows=rows,
            section=path[1:],
            title={
                "/trends": "Tendencias",
                "/alerts": "Alertas",
                "/history": "Decisiones editoriales",
            }[path],
        )

    @app.get("/admin/{section}", response_class=HTMLResponse)
    def admin_page(request: Request, section: str, user=Depends(require("media_admin"))):
        editorial_sections = {"sources", "config", "users"}
        global_sections = {"providers", "prompts", "operations", "audit"}
        if section not in editorial_sections | global_sections:
            raise HTTPException(404)
        if section in global_sections and user.role != "superadmin":
            raise HTTPException(403)
        with db.session() as session:
            version, config = active_config(session)
            model = {
                "sources": Source,
                "users": User,
                "prompts": Prompt,
                "operations": Job,
                "audit": Audit,
                "config": ConfigVersion,
                "providers": APIUsage,
            }[section]
            rows = [
                row_dict(x, ("password_hash",))
                for x in session.scalars(
                    select(model).order_by(model.__table__.c.id.desc()).limit(100)
                )
            ]
            providers = list(session.scalars(select(Secret.name)))
            incidents = (
                [
                    s.value
                    for s in session.scalars(
                        select(State).where(State.key.like("source_incident:%"))
                    )
                ]
                if section in ("operations", "sources")
                else []
            )
        return render(
            request,
            "admin.html",
            section=section,
            rows=rows,
            config=config.model_dump(),
            config_json=json.dumps(config.model_dump(), ensure_ascii=False, indent=2),
            version=version,
            providers=providers,
            incidents=incidents,
            backups=sorted(
                p.name
                for p in settings.backup_dir.glob("agenda-*.db")
                if re.fullmatch(r"agenda-[0-9]{19}\.db", p.name)
            )
            if section == "operations"
            else [],
            title={
                "sources": "Fuentes",
                "config": "Criterios y pesos",
                "users": "Equipo",
                "providers": "Proveedores",
                "prompts": "Prompts",
                "operations": "Operaciones",
                "audit": "Auditoría",
            }[section],
        )

    def demo_job(result, user_id):
        with db.session() as session:
            job = Job(kind="demo", payload={}, status="done", result=result,
                      idempotency_key=secrets.token_hex(16), user_id=user_id)
            session.add(job)
            session.flush()
            return {"job_id": job.id}

    if settings.demo_mode:
        @app.get("/api/v1/demo/status")
        def demo_status(user=Depends(require())):
            with db.session() as session:
                return session.get(State, "demo_scenario").value

        @app.post("/api/v1/demo/reset")
        def demo_reset(user=Depends(require("media_admin"))):
            from .demo_data import seed
            with db.session() as session:
                return seed(session, settings.demo_epoch, settings.app_base_url, reset=True)

        @app.post("/api/v1/demo/news")
        def demo_news(user=Depends(require("media_admin"))):
            from .demo_data import simulate_news
            with db.session() as session:
                return simulate_news(session, settings.demo_epoch, settings.app_base_url)

        @app.get("/integrations", response_class=HTMLResponse)
        def demo_integrations(request: Request, user=Depends(require())):
            return render(request, "demo_integrations.html", title="Integraciones de la demo")

        @app.get("/evidence/{document_id}", response_class=HTMLResponse)
        def demo_evidence(document_id: int, request: Request, user=Depends(require())):
            with db.session() as session:
                document = session.get(Document, document_id)
                if not document:
                    raise HTTPException(404, "Evidencia inexistente")
                data = row_dict(document)
                mention = session.get(Mention, document_id)
                event_id = mention.event_id if mention else None
            return render(request, "demo_evidence.html", document=data, event_id=event_id,
                          title="Evidencia ficticia")

    if settings.demo_enabled and not settings.demo_mode:
        from .demo import DemoManager
        manager = DemoManager(settings)
        app.state.demo_manager = manager
        app.mount("/demo", manager)
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def demo_lifespan(_app):
            await manager.start()
            try:
                yield
            finally:
                await manager.stop()

        app.router.lifespan_context = demo_lifespan

    return app
