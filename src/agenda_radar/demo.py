"""Isolated, bounded demo visits mounted under /demo. Never opens the production DB."""

import asyncio
import contextlib
import re
import secrets
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from .config import Settings
from .demo_data import seed
from .models import User
from .security import digest

ROOT = Path(__file__).parent
COOKIE = "radar_demo_visit"


@dataclass
class Visit:
    app: FastAPI
    directory: Path
    expires: float
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    writes: int = 0


class DemoManager:
    def __init__(self, settings):
        self.settings = settings
        self.root = settings.demo_dir.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.visits: dict[str, Visit] = {}
        self.lock = asyncio.Lock()
        self.cleaner = None
        self.login_attempts: list[float] = []
        self.templates = Jinja2Templates(directory=ROOT / "templates")
        self.templates.env.globals.update(base_path="/demo", demo=True, demo_enabled=True)
        self.static = StaticFiles(directory=ROOT / "static")

    async def start(self):
        # Visits intentionally expire on service restart; only owned directory names qualify.
        for path in self.root.iterdir():
            if re.fullmatch(r"visit-[a-f0-9]{64}", path.name) and not path.is_symlink():
                await run_in_threadpool(shutil.rmtree, path)
        self.cleaner = asyncio.create_task(self.cleanup_loop())

    async def stop(self):
        if self.cleaner:
            self.cleaner.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.cleaner
        for key in list(self.visits):
            await self.remove(key)

    async def cleanup_loop(self):
        while True:
            await asyncio.sleep(600)
            await self.cleanup()

    async def remove(self, key):
        visit = self.visits.pop(key, None)
        if visit:
            visit.app.state.db.engine.dispose()
            await run_in_threadpool(shutil.rmtree, visit.directory, True)

    async def cleanup(self):
        async with self.lock:
            for key, visit in list(self.visits.items()):
                if visit.expires <= time.time() and not visit.lock.locked():
                    await self.remove(key)

    def build_visit(self, key):
        from .app import create_app

        now = time.time()
        directory = self.root / ("visit-" + key)
        config = Settings(  # type: ignore[call-arg]
            _env_file=None,
            demo_mode=True,
            demo_enabled=False,
            demo_epoch=now,
            data_dir=directory / "data",
            secrets_dir=directory / "secrets",
            backup_dir=directory / "backups",
            app_base_url=self.settings.app_base_url.rstrip("/") + "/demo",
            cookie_secure=self.settings.cookie_secure,
            session_hours=2,
        )
        app = create_app(config)
        app.state.db.migrate()
        # Public demo credential only. Normal hash_password/create_user policies stay unchanged.
        from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

        password_hash = Argon2id(
            salt=secrets.token_bytes(16), length=32, iterations=2, lanes=1, memory_cost=19456
        ).derive_phc_encoded(b"demo")
        with app.state.db.session() as session:
            session.add(User(email="demo", password_hash=password_hash, role="media_admin"))
            session.flush()
            seed(session, now, config.app_base_url)
        return Visit(app, directory, now + self.settings.demo_session_seconds)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return
        local = dict(scope)
        path = scope["path"]
        if path == "/demo" or path.startswith("/demo/"):
            path = path[len("/demo") :] or "/"
        local.update(path=path, raw_path=path.encode(), root_path="")
        request = Request(local, receive)
        response: Response
        method = scope["method"]
        key = digest(request.cookies.get(COOKIE, ""))
        if path.startswith("/static/"):
            static_scope = {**local, "path": path[len("/static") :], "root_path": ""}
            await self.static(static_scope, receive, send)
            return
        if path == "/login" and method == "GET":
            response = self.templates.TemplateResponse(
                request=request, name="login.html", context={"csrf": ""}
            )
            await response(local, receive, send)
            return
        await self.cleanup()
        new_token = None
        if path == "/api/v1/auth/login" and method == "POST":
            if request.headers.get("x-requested-with") != "AgendaRadar":
                await JSONResponse({"detail": "Solicitud inválida (CSRF)"}, 403)(
                    local, receive, send
                )
                return
            origin = request.headers.get("origin")
            if origin and origin != str(request.base_url).rstrip("/"):
                await JSONResponse({"detail": "Origen no permitido"}, 403)(local, receive, send)
                return
            body = b""
            async for chunk in request.stream():
                body += chunk
                if len(body) > 4096:
                    await JSONResponse({"detail": "Solicitud demasiado grande"}, 413)(
                        local, receive, send
                    )
                    return
            import json

            try:
                credentials = json.loads(body)
                valid = (
                    isinstance(credentials, dict)
                    and credentials.get("email") == "demo"
                    and credentials.get("password") == "demo"
                )
            except (ValueError, TypeError):
                valid = False
            if not valid:
                await JSONResponse({"detail": "Usá usuario demo y contraseña demo"}, 401)(
                    local, receive, send
                )
                return
            async with self.lock:
                self.login_attempts = [at for at in self.login_attempts if at > time.time() - 60]
                if len(self.login_attempts) >= 20:
                    await JSONResponse(
                        {"detail": "Esperá un minuto antes de volver a ingresar"}, 429
                    )(local, receive, send)
                    return
                self.login_attempts.append(time.time())
                if key not in self.visits:
                    if len(self.visits) >= self.settings.demo_max_sessions:
                        await JSONResponse(
                            {"detail": "La demo está completa. Volvé a intentar más tarde."}, 503
                        )(local, receive, send)
                        return
                    new_token = secrets.token_urlsafe(32)
                    key = digest(new_token)
                    self.visits[key] = await run_in_threadpool(self.build_visit, key)
            sent_body = False
            original_receive = receive

            async def replay():
                nonlocal sent_body
                if not sent_body:
                    sent_body = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await original_receive()

            receive = replay
        visit = self.visits.get(key)
        if not visit:
            response = (
                JSONResponse({"detail": "La demo venció. Ingresá nuevamente con demo / demo."}, 401)
                if path.startswith("/api/")
                else RedirectResponse("/demo/login", 303)
            )
            response.delete_cookie(COOKIE, path="/demo")
            await response(local, receive, send)
            return
        async with visit.lock:
            # Recheck after waiting; another request may have logged out this visitor.
            if key not in self.visits or visit.expires <= time.time():
                await JSONResponse({"detail": "La demo venció. Volvé a ingresar."}, 401)(
                    local, receive, send
                )
                return
            if method not in ("GET", "HEAD", "OPTIONS"):
                visit.writes += 1
                if visit.writes > 250 and path not in ("/api/v1/auth/logout", "/api/v1/demo/reset"):
                    await JSONResponse(
                        {"detail": "Límite de cambios de la demo. Reiniciá el escenario."}, 429
                    )(local, receive, send)
                    return
            status = 500

            async def wrapped_send(message):
                nonlocal status
                if message["type"] == "http.response.start":
                    status = message["status"]
                    if new_token and status < 400:
                        cookie = JSONResponse({})
                        cookie.set_cookie(
                            COOKIE,
                            new_token,
                            path="/demo",
                            httponly=True,
                            secure=self.settings.cookie_secure,
                            samesite="strict",
                            max_age=self.settings.demo_session_seconds,
                        )
                        message["headers"] += [
                            (b"set-cookie", cookie.headers["set-cookie"].encode())
                        ]
                await send(message)

            await visit.app(local, receive, wrapped_send)
            if path == "/api/v1/demo/reset" and status == 200:
                visit.writes = 0
            if (path == "/api/v1/auth/logout" and status == 200) or (new_token and status >= 400):
                await self.remove(key)
