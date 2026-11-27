"""Public marketing, SEO, health, setup and authentication routes."""

import secrets
import time

from fastapi import Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from ..i18n import language
from ..models import LoginSession, State, User
from ..security import audit, digest, hash_password, verify_password
from ..seo import localized_url, sitemap


class LoginInput(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)


class PasswordInput(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class SetupInput(LoginInput):
    code: str = Field(min_length=20, max_length=100)


PUBLIC_PAGE_META = {
    "home": (
        "Agenda editorial y monitoreo para redacciones",
        "Dejá de revisar 40 pestañas antes de la reunión de pauta. Detectá brechas de cobertura, coordiná en Slack o Telegram y elegí OpenAI, Claude o IA local.",
    ),
    "about": (
        "Criterio editorial humano, evidencia trazable",
        "Por qué construimos Agenda Radar: una plataforma self-hosted por redacción que conecta fuentes, brechas de agenda y seguimiento entre turnos.",
    ),
    "funcionalidades": (
        "Agrupamiento, brechas, agentes, Slack, Telegram e IA",
        "Conocé cómo Agenda Radar agrupa noticias por acontecimiento, compara cobertura propia vs referencias y lleva alertas y briefings a Slack, Telegram o Web.",
    ),
    "casos-de-uso": (
        "Seis beneficios concretos para tu redacción",
        "Del pase de pauta en 10 minutos al seguimiento entre turnos y la IA local sin salida a la nube: seis escenarios reales para redacciones.",
    ),
    "roadmap": (
        "Para tu redacción: agentes, canales y puesta en marcha",
        "Activá packs de fuentes, delegá vigilancia y briefing en tres agentes editoriales y coordiná decisiones en Slack, Telegram o Web.",
    ),
}


def install_public_routes(app, db, settings, templates, require, render, session_cookie="radar_session"):
    def public_page(request, page="home"):
        title, description = PUBLIC_PAGE_META[page]
        return templates.TemplateResponse(
            request=request,
            name="public.html",
            context={
                "page": page,
                "title": title,
                "description": description,
                "public_url": localized_url(settings.app_base_url, "/" + page, language.get()),
                "alternate_urls": {
                    lang: localized_url(settings.app_base_url, "/" + page, lang)
                    for lang in ("en", "es")
                },
            },
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
                if settings.collaboration_enabled:
                    collaboration_pulse = session.get(State, "collaboration_heartbeat")
                    healthy = healthy and bool(
                        collaboration_pulse and time.time() - collaboration_pulse.value["at"] < 120
                    )
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
            for login in session.scalars(select(LoginSession).where(LoginSession.user_id == user.id)):
                session.delete(login)
            audit(session, user.id, "password_changed", "user", user.id)
        return {"status": "changed"}

    @app.get("/setup", response_class=HTMLResponse)
    def setup_page(request: Request):
        with db.session() as session:
            if session.scalar(select(User.id).limit(1)):
                return RedirectResponse("/login", status_code=303)
        return templates.TemplateResponse(request=request, name="setup.html", context={})

    @app.post("/api/v1/auth/setup")
    def setup(payload: SetupInput):
        from ..bootstrap import enroll

        enroll(db, payload.code, payload.email, payload.password)
        (settings.secrets_dir / "setup-code").unlink(missing_ok=True)
        return {"status": "created"}

    @app.post("/api/v1/auth/login")
    def login(payload: LoginInput, request: Request):
        if settings.demo_enabled and payload.email == "demo" and payload.password == "demo":
            return {"redirect": "/demo/"}
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
            valid = bool(user and user.enabled and verify_password(payload.password, user.password_hash))
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
            path="/",
            httponly=True,
            secure=settings.cookie_secure,
            samesite="strict",
            max_age=settings.session_hours * 3600,
        )
        return response

    @app.post("/api/v1/auth/logout")
    def logout(request: Request, user=Depends(require())):
        with db.session() as session:
            login_row = session.get(LoginSession, digest(request.cookies[session_cookie]))
            session.delete(login_row)
        response = JSONResponse({"ok": True})
        response.delete_cookie(session_cookie, path="/")
        return response

    @app.get("/api/v1/auth/me")
    def me(request: Request, user=Depends(require())):
        return {"id": user.id, "email": user.email, "role": user.role, "csrf": request.state.csrf}

    @app.get("/api/v1/openapi.json")
    def schema(user=Depends(require())):
        return app.openapi()

    @app.get("/robots.txt", response_class=PlainTextResponse)
    def robots():
        return "User-agent: *\nAllow: /\nDisallow: /api/\nSitemap: " + settings.app_base_url.rstrip("/") + "/sitemap.xml\n"

    @app.get("/sitemap.xml")
    def public_sitemap():
        return PlainTextResponse(sitemap(settings.app_base_url), media_type="application/xml")

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

    return public_page
