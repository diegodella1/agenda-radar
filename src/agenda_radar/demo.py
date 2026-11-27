"""Isolated, bounded demo visits mounted under /demo. Never opens the production DB."""

import asyncio
import contextlib
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import sqlite3
import threading
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
        from .app import ASSET_VERSION, ASSET_VERSIONS

        self.settings = settings
        self.root = settings.demo_dir.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.visits: dict[str, Visit] = {}
        self.pending: dict[str, asyncio.Task] = {}
        self.failed: dict[str, float] = {}
        self.build_lock = asyncio.Lock()
        self.lock = asyncio.Lock()
        self.cleaner = None
        self.preloader = None
        self.stopping = asyncio.Event()
        self.template_lock = threading.Lock()
        self.template_path = self.root / "prepared.db"
        code = hashlib.sha256()
        for source in sorted(ROOT.rglob("*.py")):
            code.update(source.relative_to(ROOT).as_posix().encode())
            code.update(source.read_bytes())
        code.update(settings.app_base_url.encode())
        self.template_version = code.hexdigest()
        self.login_attempts: list[float] = []
        self.templates = Jinja2Templates(directory=ROOT / "templates")
        from .i18n import language, translate

        self.templates.env.globals["_"] = translate
        self.templates.env.filters["tr"] = translate
        self.templates.context_processors.append(lambda request: {"language": language.get()})
        self.templates.env.globals.update(
            base_path="/demo", demo=True, demo_enabled=True, asset_version=ASSET_VERSION,
            asset_url=lambda name: f"/demo/static/{name}?v={ASSET_VERSIONS[name]}",
        )
        self.static = StaticFiles(directory=ROOT / "static")

    async def start(self):
        # Visits intentionally expire on service restart; only owned directory names qualify.
        for path in self.root.iterdir():
            if re.fullmatch(r"visit-(?:[a-f0-9]{64}|template-[a-f0-9]{32})", path.name) and not path.is_symlink():
                await run_in_threadpool(shutil.rmtree, path)
        self.cleaner = asyncio.create_task(self.cleanup_loop())
        self.stopping.clear()
        self.preloader = asyncio.create_task(self.preload_loop())

    async def stop(self):
        self.stopping.set()
        if self.preloader:
            await self.preloader
        if self.cleaner:
            self.cleaner.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.cleaner
        if self.pending:
            await asyncio.gather(*self.pending.values(), return_exceptions=True)
            await self.cleanup()
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
            for key, task in list(self.pending.items()):
                if task.done():
                    del self.pending[key]
                    try:
                        self.visits[key] = task.result()
                    except Exception:
                        logging.getLogger(__name__).exception("demo_preparation_failed")
                        self.failed[key] = time.time() + self.settings.demo_session_seconds
            self.failed = {key: expires for key, expires in self.failed.items() if expires > time.time()}
            for key, visit in list(self.visits.items()):
                if visit.expires <= time.time() and not visit.lock.locked():
                    await self.remove(key)

    async def prepare_visit(self, key):
        async with self.build_lock:
            try:
                visit = await run_in_threadpool(self.build_visit, key)
                visit.expires = time.time() + self.settings.demo_session_seconds
                return visit
            except Exception:
                await run_in_threadpool(shutil.rmtree, self.root / ("visit-" + key), True)
                raise

    async def preload_loop(self):
        while not self.stopping.is_set():
            try:
                await run_in_threadpool(self.refresh_template)
            except Exception:
                logging.getLogger(__name__).exception("demo_template_failed")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self.stopping.wait(), timeout=30)

    def template_metadata(self, connection):
        row = connection.execute("SELECT payload FROM prepared_demo").fetchone()
        metadata = json.loads(row[0])
        if metadata["version"] != self.template_version:
            raise ValueError("Incompatible demo template")
        return metadata

    def refresh_template(self):
        from .demo_corpus import read_snapshot

        with self.template_lock:
            payload = read_snapshot(self.settings.demo_corpus_dir)
            snapshot_id = payload["snapshot_id"] if payload else None
            try:
                with contextlib.closing(sqlite3.connect(
                    self.template_path.as_uri() + "?mode=ro", uri=True
                )) as connection:
                    metadata = self.template_metadata(connection)
                    if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                        raise ValueError("Invalid demo template")
                    if metadata["snapshot_id"] == snapshot_id or payload is None:
                        return
            except (sqlite3.Error, ValueError, KeyError, TypeError):
                pass
            key = "template-" + secrets.token_hex(16)
            directory = self.root / ("visit-" + key)
            temporary = directory / "prepared.db"
            visit = None
            started = time.monotonic()
            try:
                visit = self.build_seed(key, payload)
                with contextlib.closing(sqlite3.connect(visit.app.state.db.path)) as source:
                    with contextlib.closing(sqlite3.connect(temporary)) as target:
                        source.backup(target)
                temporary.chmod(0o600)
                with contextlib.closing(sqlite3.connect(temporary)) as connection:
                    connection.execute("PRAGMA journal_mode=DELETE")
                    connection.execute("CREATE TABLE prepared_demo (payload TEXT NOT NULL)")
                    connection.execute("INSERT INTO prepared_demo VALUES (?)", (json.dumps({
                        "version": self.template_version, "snapshot_id": snapshot_id,
                        "epoch": visit.app.state.settings.demo_epoch,
                    }),))
                    connection.commit()
                    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise ValueError("Invalid prepared demo")
                with temporary.open("rb") as stream:
                    os.fsync(stream.fileno())
                os.replace(temporary, self.template_path)
                descriptor = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                logging.getLogger(__name__).info(
                    "demo_template_ready seconds=%.3f", time.monotonic() - started
                )
            finally:
                if visit:
                    visit.app.state.db.engine.dispose()
                shutil.rmtree(directory, ignore_errors=True)

    def build_visit(self, key):
        from .app import create_app

        directory = self.root / ("visit-" + key)
        destination = directory / "data" / "agenda.db"
        destination.parent.mkdir(parents=True, mode=0o700)
        # Open the immutable file before publication can replace its pathname.
        try:
            source = sqlite3.connect(self.template_path.as_uri() + "?mode=ro", uri=True)
            try:
                metadata = self.template_metadata(source)
            except Exception:
                source.close()
                raise
        except (sqlite3.Error, ValueError, KeyError, TypeError):
            self.refresh_template()
            source = sqlite3.connect(self.template_path.as_uri() + "?mode=ro", uri=True)
            metadata = self.template_metadata(source)
        with contextlib.closing(source), contextlib.closing(sqlite3.connect(destination)) as target:
            # Visits are disposable on restart. Application connections restore their configured durability.
            target.execute("PRAGMA synchronous=OFF")
            source.backup(target)
            target.execute("PRAGMA journal_mode=WAL")
        destination.chmod(0o600)
        app = create_app(self.visit_config(directory, metadata["epoch"]))
        return Visit(app, directory, time.time() + self.settings.demo_session_seconds)

    def visit_config(self, directory, epoch):
        return Settings(  # type: ignore[call-arg]
            _env_file=None,
            demo_mode=True,
            demo_enabled=False,
            demo_epoch=epoch,
            demo_corpus_dir=self.settings.demo_corpus_dir,
            data_dir=directory / "data",
            secrets_dir=directory / "secrets",
            backup_dir=directory / "backups",
            app_base_url=self.settings.app_base_url.rstrip("/") + "/demo",
            default_language=self.settings.default_language,
            cookie_secure=self.settings.cookie_secure,
            session_hours=2,
        )

    def build_seed(self, key, payload):
        from .app import create_app

        now = time.time()
        directory = self.root / ("visit-" + key)
        config = self.visit_config(directory, payload["captured_at"] if payload else now)
        app = create_app(config)
        try:
            app.state.db.migrate()
            # Public demo credential only. Normal hash_password/create_user policies stay unchanged.
            from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

            password_hash = Argon2id(
                salt=secrets.token_bytes(16), length=32, iterations=2, lanes=1, memory_cost=19456
            ).derive_phc_encoded(b"demo")
            with app.state.db.session() as session:
                session.add(User(email="demo", password_hash=password_hash, role="media_admin"))
                session.flush()
                seed(session, config.demo_epoch, config.app_base_url, payload=payload)
            return Visit(app, directory, now + self.settings.demo_session_seconds)
        except Exception:
            app.state.db.engine.dispose()
            raise

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
            if key in self.failed:
                del self.failed[key]
                response = JSONResponse({"detail": "No pudimos preparar la demo. Volvé a intentar."}, 503)
                response.delete_cookie(COOKIE, path="/demo")
                await response(local, receive, send)
                return
            async with self.lock:
                self.login_attempts = [at for at in self.login_attempts if at > time.time() - 60]
                creating = key not in self.visits and key not in self.pending
                if creating and len(self.login_attempts) >= 20:
                    await JSONResponse(
                        {"detail": "Esperá un minuto antes de volver a ingresar"}, 429
                    )(local, receive, send)
                    return
                if creating:
                    self.login_attempts.append(time.time())
                    if len(self.visits) + len(self.pending) >= self.settings.demo_max_sessions:
                        await JSONResponse(
                            {"detail": "La demo está completa. Volvé a intentar más tarde."}, 503
                        )(local, receive, send)
                        return
                    new_token = secrets.token_urlsafe(32)
                    key = digest(new_token)
                    self.pending[key] = asyncio.create_task(self.prepare_visit(key))
            if creating and key in self.pending:
                # A timeout must not cancel the copy that subsequent requests await.
                await asyncio.wait({self.pending[key]}, timeout=1)
                await self.cleanup()
            if key in self.failed:
                del self.failed[key]
                response = JSONResponse({"detail": "No pudimos preparar la demo. Volvé a intentar."}, 503)
                response.delete_cookie(COOKIE, path="/demo")
                await response(local, receive, send)
                return
            if key in self.pending:
                response = JSONResponse({"pending": True, "detail": "Preparando tu demo con noticias reales…"}, 202)
                response.headers["Retry-After"] = "2"
                if new_token:
                    response.set_cookie(COOKIE, new_token, path="/demo", httponly=True,
                                        secure=self.settings.cookie_secure, samesite="strict",
                                        max_age=self.settings.demo_session_seconds)
                await response(local, receive, send)
                return
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
