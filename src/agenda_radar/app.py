import hashlib
import secrets
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import select
from starlette.middleware.gzip import GZipMiddleware

from .config import Settings
from .db import Database
from .events import merge_events, split_event
from .jobs import enqueue
from .models import (
    Alert,
    Decision,
    Document,
    Event,
    Job,
    LoginSession,
    Mention,
    OwnCoverage,
    Source,
    State,
    TrendSample,
    User,
)
from .presentation import editorial_view
from .routes.admin import install_admin_routes
from .routes.public import install_public_routes
from .schemas import DecisionInput, QueryInput
from .scoring import WINDOWS, compare, source_healthy
from .security import ROLES, Vault, audit, digest, pairing_code
from .seo import PUBLIC_PATHS

ROOT = Path(__file__).parent
ASSET_VERSIONS = {
    str(path.relative_to(ROOT / "static")): hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    for path in sorted((ROOT / "static").rglob("*"))
    if path.is_file()
}
ASSET_VERSION = digest("".join(ASSET_VERSIONS.values()))[:12]


def row_dict(row, exclude=()):
    return {
        column.name: getattr(row, column.name)
        for column in row.__table__.columns
        if column.name not in exclude
    }


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


def create_app(settings: Settings | None = None):
    settings = settings or Settings()
    db = Database(settings.database_path)
    vault = Vault(settings.secrets_dir)
    base_path = ""
    session_cookie = "radar_session"
    app = FastAPI(
        title="Agenda Radar", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None
    )
    app.state.db, app.state.settings, app.state.vault = db, settings, vault
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    templates = Jinja2Templates(directory=ROOT / "templates")
    templates.env.globals.update(
        base_path=base_path,
        demo=False,
        demo_enabled=settings.demo_enabled,
        asset_version=ASSET_VERSION,
        asset_url=lambda name: f"/static/{name}?v={ASSET_VERSIONS[name]}",
    )
    templates.env.filters["date"] = lambda value: (
        datetime.fromtimestamp(value, ZoneInfo(settings.app_timezone)).strftime("%d/%m %H:%M")
        if value
        else "Sin registro"
    )
    templates.env.filters["pct"] = lambda value: f"{value:.1f}" if value is not None else "—"
    from .i18n import language, request_language, translate

    templates.env.globals["_"] = translate
    templates.env.globals["demo_showcase"] = True
    templates.env.filters["tr"] = translate
    templates.context_processors.append(lambda request: {"language": language.get()})
    original_date = templates.env.filters["date"]
    templates.env.filters["date"] = lambda value: translate(original_date(value))

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
        demo_dispatch = settings.demo_enabled and (
            request.url.path == "/demo" or request.url.path.startswith("/demo/")
        )
        public_asset = request.url.path.startswith("/static/")
        token = None if demo_dispatch or public_asset else request.cookies.get(session_cookie)
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
        response = await call_next(request)
        indexable = request.url.path in PUBLIC_PATHS or (
            request.url.path == "/" and not request.state.user
        )
        if not indexable and not request.url.path.startswith("/static/"):
            response.headers["X-Robots-Tag"] = "noindex, follow"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if settings.cookie_secure and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if request.url.path.startswith(("/static/", "/demo/static/")) and response.status_code < 400:
            asset_name = request.url.path.split("/static/", 1)[1]
            version = request.query_params.get("v")
            response.headers["Cache-Control"] = (
                "public, max-age=31536000, immutable"
                if version and version == ASSET_VERSIONS.get(asset_name)
                else "public, max-age=0, must-revalidate"
            )
        else:
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.middleware("http")
    async def language_middleware(request, call_next):
        selected = request_language(request, settings.default_language)
        token = language.set(selected)
        try:
            response = await call_next(request)
            if not request.url.path.startswith(("/static/", "/demo/static/")):
                response.headers["Content-Language"] = selected
                if request.query_params.get("lang") in {"en", "es"}:
                    response.set_cookie(
                        "radar_lang",
                        selected,
                        max_age=31536000,
                        secure=settings.cookie_secure,
                        samesite="lax",
                    )
            return response
        finally:
            language.reset(token)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        if exc.status_code == 401 and request.method == "GET" and request.url.path == "/collaboration":
            from urllib.parse import urlencode

            destination = request.url.path + ("?" + request.url.query if request.url.query else "")
            return RedirectResponse("/login?" + urlencode({"next": destination}), status_code=303)
        return JSONResponse(
            {"detail": translate(exc.detail)}, status_code=exc.status_code, headers=exc.headers
        )

    @app.exception_handler(ValueError)
    async def bad_value(request, exc):
        return JSONResponse({"detail": translate(str(exc))}, status_code=422)

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

    def render(request, template, **context):
        if not request.state.user:
            return RedirectResponse("/login", status_code=303)
        return templates.TemplateResponse(
            request=request,
            name=template,
            context={
                "user": request.state.user,
                "csrf": request.state.csrf,
                "roles": ROLES,
                "now": time.time(),
                **context,
            },
        )

    public_page = install_public_routes(
        app, db, settings, templates, require, render, session_cookie=session_cookie
    )
    install_admin_routes(app, db, vault, settings, require, render, row_dict)

    from .collaboration_api import install

    install(app, db, vault, settings, require, render)

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
                session, window, topic=topic, source=source, channel=channel, geo=geo
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
            result = compare(session, window)
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
            if payload.action in ("follow", "dismiss"):
                from .collaboration_models import EditorialFollowup

                follow = session.get(EditorialFollowup, payload.event_id) or EditorialFollowup(
                    event_id=payload.event_id
                )
                follow.status = "following" if payload.action == "follow" else "dismissed"
                follow.updated_at = time.time()
                session.add(follow)
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
        with db.session() as session:
            if not session.get(Event, payload.event_id):
                raise HTTPException(404, "Acontecimiento inexistente")
            session.add(
                OwnCoverage(
                    **{**payload.model_dump(), "url": canonical_url(payload.url)}, user_id=user.id
                )
            )
            audit(session, user.id, "coverage", "event", payload.event_id, after=payload.model_dump())
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
        return {
            "job_id": enqueue(
                db,
                "query",
                {**payload.model_dump(), "language": language.get()},
                secrets.token_hex(16),
                user.id,
            )
        }

    @app.get("/api/v1/jobs/{job_id}")
    def job_status(job_id: int, user=Depends(require())):
        with db.session() as session:
            job = session.get(Job, job_id)
            if not job or (job.user_id != user.id and user.role != "superadmin"):
                raise HTTPException(404, "Trabajo inexistente")
            return row_dict(job)

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

    @app.get("/api/v1/export/agenda.md")
    def export(window="24h", user=Depends(require("analyst"))):
        if window not in WINDOWS:
            raise ValueError("Ventana inválida")
        with db.session() as session:
            result = compare(session, window)
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

    @app.get("/", response_class=HTMLResponse)
    @app.get("/compare", response_class=HTMLResponse)
    @app.get("/events", response_class=HTMLResponse)
    def dashboard(request: Request, window="24h", topic="", source="", channel="", geo=""):
        if request.url.path == "/" and not request.state.user:
            return public_page(request)
        if window not in WINDOWS:
            window = "24h"
        with db.session() as session:
            data = editorial_view(
                session, window, topic=topic, source=source, channel=channel, geo=geo
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
            comparison = editorial_view(session, window)
            has_filters = any((topic, source, channel, geo))
            context = (
                editorial_view(session, window, topic=topic, source=source, channel=channel, geo=geo)
                if has_filters
                else comparison
            )
            score = next((r for r in comparison["rows"] if r["event_id"] == event_id), None)
            from .ingest import stemmed_tokens

            ev_stems = stemmed_tokens(data["label"])
            since = time.time() - WINDOWS[window]
            related_trends = []
            for sample in session.scalars(
                select(TrendSample)
                .where(TrendSample.captured_at >= since)
                .order_by(TrendSample.captured_at.desc())
                .limit(100)
            ):
                if ev_stems & stemmed_tokens(sample.label):
                    related_trends.append(row_dict(sample))
                    if len(related_trends) >= 5:
                        break
            related_x = []
            for xdoc in session.scalars(
                select(Document)
                .where(Document.channel == "x", Document.observed_at >= since)
                .order_by(Document.observed_at.desc())
                .limit(100)
            ):
                if len(ev_stems & stemmed_tokens(xdoc.title)) >= 2:
                    related_x.append(row_dict(xdoc))
                    if len(related_x) >= 5:
                        break
            other_events = [
                {"id": ev.id, "label": ev.label}
                for ev in session.scalars(
                    select(Event)
                    .where(Event.status == "active", Event.id != event_id)
                    .order_by(Event.id.desc())
                    .limit(50)
                )
            ]
        data["related_trends"] = related_trends
        data["related_x"] = related_x
        data["other_events"] = other_events
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

    if settings.demo_enabled:
        from .showcase import create_showcase

        app.mount("/demo", create_showcase(templates))

    return app
