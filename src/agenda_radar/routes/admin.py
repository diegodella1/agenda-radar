"""Administrative APIs and HTML views (sources, criteria, users, providers, prompts, ops, audit)."""

import csv
import io
import json
import re
import secrets
import time

from fastapi import Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from ..editorial import active_config, publish_config
from ..ingest import store_document
from ..jobs import enqueue
from ..models import (
    APIUsage,
    Audit,
    ConfigVersion,
    Job,
    Prompt,
    Secret,
    Source,
    State,
    TrendSample,
    User,
)
from ..schemas import DocumentInput, EditorialConfig, SourceInput, UserInput
from ..scoring import compare
from ..security import ROLES, audit, create_user, digest


class ConfigInput(BaseModel):
    config: EditorialConfig
    reason: str = Field(min_length=3, max_length=1000)


class SecretInput(BaseModel):
    name: str
    value: str = Field(min_length=5, max_length=2000)


class PromptInput(BaseModel):
    purpose: str = "answer_telegram"
    template: str = Field(min_length=10, max_length=10000)
    model: str = Field(min_length=1, max_length=100)


def install_admin_routes(app, db, vault, settings, require, render, row_dict):
    @app.get("/api/v1/admin/sources")
    def list_sources(user=Depends(require("media_admin"))):
        with db.session() as session:
            return [row_dict(s) for s in session.scalars(select(Source).order_by(Source.id))]

    @app.post("/api/v1/admin/sources")
    def add_source(payload: SourceInput, user=Depends(require("media_admin"))):
        with db.session() as session:
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
            audit(session, user.id, "edit", "source", source.id, before=before, after=payload.model_dump())
        return {"ok": True}

    @app.get("/api/v1/admin/sources/packs")
    def source_packs(user=Depends(require("media_admin"))):
        from ..starter_packs import list_packs

        return list_packs()

    @app.post("/api/v1/admin/sources/packs/{pack_id}/apply")
    def apply_source_pack(pack_id: str, user=Depends(require("media_admin"))):
        from ..starter_packs import apply_pack

        with db.session() as session:
            result = apply_pack(session, pack_id)
            audit(session, user.id, "apply_pack", "source", pack_id, after=result)
        return result

    @app.get("/api/v1/admin/sources/export.csv")
    def export_sources(user=Depends(require("media_admin"))):
        fields = [
            "name", "kind", "channel", "url", "scope", "group_name",
            "weight", "poll_interval", "country", "legal_basis", "enabled",
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
        return {
            "job_id": enqueue(db, "test_source", payload.model_dump(), secrets.token_hex(16), user.id)
        }

    @app.post("/api/v1/admin/sources/{source_id}/poll")
    def force_poll(source_id: int, user=Depends(require("media_admin"))):
        with db.session() as session:
            if not session.get(Source, source_id):
                raise HTTPException(404, "Fuente inexistente")
        return {
            "job_id": enqueue(
                db, "poll", {"source_id": source_id},
                f"manual-poll:{source_id}:{int(time.time() // 60)}", user.id,
            )
        }

    @app.post("/api/v1/admin/sources/{source_id}/documents")
    def import_document(source_id: int, payload: DocumentInput, user=Depends(require("media_admin"))):
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
                    for v in session.scalars(select(ConfigVersion).order_by(ConfigVersion.id.desc()).limit(50))
                ],
            }

    def check_global_config(session, new, user):
        _, old = active_config(session)
        keys = (
            "ai_enabled", "extraction_enabled", "extraction_model",
            "extraction_input_usd_million", "extraction_output_usd_million",
            "telegram_enabled", "ai_model", "ai_input_usd_million",
            "ai_output_usd_million", "daily_budget_usd", "monthly_budget_usd", "run_enabled",
        )
        if user.role != "superadmin" and any(getattr(new, key) != getattr(old, key) for key in keys):
            raise HTTPException(403, "Solo superadmin cambia proveedores y límites globales")

    @app.post("/api/v1/admin/config/preview")
    def preview(payload: ConfigInput, user=Depends(require("media_admin"))):
        with db.session() as session:
            check_global_config(session, payload.config, user)
            fingerprint = digest(payload.config.model_dump_json())
            version, _ = active_config(session)
            session.merge(
                State(key=f"preview:{user.id}", value={"hash": fingerprint, "version": version, "at": time.time()})
            )
            return {"before": compare(session), "after": compare(session, config=payload.config)}

    @app.post("/api/v1/admin/config/publish")
    def publish(payload: ConfigInput, user=Depends(require("media_admin"))):
        with db.session() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            check_global_config(session, payload.config, user)
            preview_row = session.get(State, f"preview:{user.id}")
            current, _ = active_config(session)
            if (
                not preview_row
                or preview_row.value["hash"] != digest(payload.config.model_dump_json())
                or preview_row.value["version"] != current
                or time.time() - preview_row.value["at"] > 1800
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
            return {"version": publish_config(session, config, user.id, f"Restaurar versión {version_id}")}

    @app.get("/api/v1/admin/providers")
    def providers(user=Depends(require("superadmin"))):
        with db.session() as session:
            names = set(session.scalars(select(Secret.name)))
            return {name: "configured" if name in names else "no_credentials" for name in ("openai", "telegram", "x")}

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

    @app.post("/api/v1/admin/jobs/{job_id}/retry")
    def retry_job(job_id: int, user=Depends(require("superadmin"))):
        with db.session() as session:
            job = session.get(Job, job_id)
            if not job or job.status != "failed":
                raise ValueError("Solo trabajos fallidos pueden reintentarse")
            job.status, job.run_after, job.attempt = "pending", time.time(), 0
            audit(session, user.id, "retry", "job", job.id)
        return {"ok": True}

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
                        source_id=source.id, label=label[:2000], geo=source.country,
                        value=row.get("Search volume") or row.get("Volumen de búsquedas"),
                        unit="manual_csv_search_trend", source_url=source.url,
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
        return {"job_id": enqueue(db, "test_prompt", {"prompt_id": prompt_id}, secrets.token_hex(16), user.id)}

    @app.post("/api/v1/admin/prompts/{prompt_id}/publish")
    def publish_prompt(prompt_id: int, user=Depends(require("superadmin"))):
        with db.session() as session:
            prompt = session.get(Prompt, prompt_id)
            if not prompt or not prompt.test_result.get("passed"):
                raise ValueError("El prompt necesita una prueba IA aprobada")
            for old in session.scalars(select(Prompt).where(Prompt.purpose == prompt.purpose, Prompt.status == "published")):
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
                "incidents": [s.value for s in session.scalars(select(State).where(State.key.like("source_incident:%")))],
                "sources": [row_dict(s) for s in session.scalars(select(Source))],
                "jobs": [row_dict(j) for j in session.scalars(select(Job).order_by(Job.id.desc()).limit(100))],
            }

    @app.get("/api/v1/admin/readiness")
    def readiness(user=Depends(require("superadmin"))):
        from ..readiness import report

        return report(db, settings)

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
                "sources": Source, "users": User, "prompts": Prompt, "operations": Job,
                "audit": Audit, "config": ConfigVersion, "providers": APIUsage,
            }[section]
            rows = [
                row_dict(x, ("password_hash",))
                for x in session.scalars(select(model).order_by(model.__table__.c.id.desc()).limit(100))
            ]
            config_sources = [
                {"id": source.id, "name": source.name, "weight": source.weight, "scope": source.scope}
                for source in session.scalars(select(Source).order_by(Source.name))
            ] if section == "config" else []
            from ..starter_packs import list_packs
            starter_packs = list_packs() if section == "sources" else []
            provider_names = list(session.scalars(select(Secret.name)))
            incidents = (
                [s.value for s in session.scalars(select(State).where(State.key.like("source_incident:%")))]
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
            config_sources=config_sources,
            starter_packs=starter_packs,
            version=version,
            providers=provider_names,
            incidents=incidents,
            backups=sorted(
                p.name
                for p in settings.backup_dir.glob("agenda-*.db")
                if re.fullmatch(r"agenda-[0-9]{19}\.db", p.name)
            )
            if section == "operations"
            else [],
            title={
                "sources": "Fuentes", "config": "Criterios y pesos", "users": "Equipo",
                "providers": "Proveedores", "prompts": "Prompts", "operations": "Operaciones", "audit": "Auditoría",
            }[section],
        )
