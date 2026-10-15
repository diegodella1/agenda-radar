import asyncio
import fcntl
import hashlib
import logging
import time
import uuid

from sqlalchemy import select

from .alerts import deliver_notifications, evaluate_alerts
from .assistant import answer_query
from .config import Settings
from .db import Database
from .editorial import active_config, heartbeat
from .ingest import poll_source, source_items
from .jobs import claim, enqueue, finish, renew
from .models import Document, Prompt, Source, User
from .operational import deliver_health, evaluate_health
from .scoring import WINDOWS, snapshot
from .security import Vault
from .telegram_bot import Telegram

log = logging.getLogger("agenda.worker")


def execute_job(db, vault, settings, job):
    if job.user_id:
        with db.session() as session:
            user = session.get(User, job.user_id)
            if not user or not user.enabled:
                raise ValueError("user_disabled")
    if job.kind == "poll":
        result = poll_source(db, job.payload["source_id"], vault)
        with db.session() as session:
            _, config = active_config(session)
            documents = (
                list(
                    session.scalars(
                        select(Document).where(Document.id.in_(result.get("document_ids", [])))
                    )
                )
                if config.ai_enabled and config.extraction_enabled
                else []
            )
        for document in documents:
            enqueue(
                db,
                "enrich",
                {"document_id": document.id, "content_hash": document.content_hash},
                f"enrich:{document.id}:{document.content_hash}",
            )
        return result
    if job.kind == "enrich":
        from .enrichment import enrich_document

        return enrich_document(db, vault, job.payload["document_id"], job.payload["content_hash"])
    if job.kind == "test_source":
        source = Source(**job.payload)
        items, _ = source_items(source)
        return {"items": [item.model_dump() for item in items[:10]]}
    if job.kind in ("query", "telegram_query"):
        return answer_query(
            db,
            vault,
            job.payload["query"],
            window=job.payload.get("window", "24h"),
            purpose=job.payload.get("purpose", "answer_telegram"),
        )
    if job.kind == "test_prompt":
        with db.session() as session:
            prompt = session.get(Prompt, job.payload["prompt_id"])
            document = session.scalar(select(Document).order_by(Document.id).limit(1))
        if prompt.purpose == "extract_event":
            from .enrichment import enrich_document

            result = (
                enrich_document(
                    db, vault, document.id, document.content_hash, prompt_id=prompt.id, apply=False
                )
                if document
                else {"status": "no_corpus"}
            )
            with db.session() as session:
                prompt = session.get(Prompt, job.payload["prompt_id"])
                prompt.test_result = {
                    "passed": result["status"] == "tested",
                    "result": result,
                    "at": time.time(),
                }
                prompt.status = "tested" if prompt.test_result["passed"] else "draft"
            return result
        from .prompt_evaluation import evaluate_prompt

        result = evaluate_prompt(db, vault, prompt)
        with db.session() as session:
            prompt = session.get(Prompt, job.payload["prompt_id"])
            prompt.test_result = {**result, "at": time.time()}
            prompt.status = "tested" if result["passed"] else "draft"
        return result
    if job.kind == "maintenance":
        from .maintenance import maintain

        return maintain(db)
    if job.kind == "backup":
        path = settings.backup_dir / f"agenda-{time.time_ns()}.db"
        db.backup(path)
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        path.with_suffix(".sha256").write_text(checksum + "  " + path.name + "\n")
        from .maintenance import rotate_backups

        rotate_backups(settings.backup_dir)
        return {"file": path.name, "sha256": checksum}
    raise ValueError("unknown_job")


def schedule(db):
    with db.session() as session:
        heartbeat(session)
        evaluate_health(session)
        _, config = active_config(session)
        sources = (
            list(
                session.scalars(
                    select(Source).where(
                        Source.enabled.is_(True),
                        Source.next_poll <= time.time(),
                        Source.kind != "manual",
                    )
                )
            )
            if config.run_enabled
            else []
        )
    enqueue(db, "maintenance", {}, f"maintenance:{int(time.time() // 86400)}")
    enqueue(db, "backup", {}, f"backup:{int(time.time() // 86400)}")
    for source in sources:
        enqueue(
            db,
            "poll",
            {"source_id": source.id},
            f"poll:{source.id}:{int(time.time() // source.poll_interval)}",
        )


def recalculate(db):
    with db.session() as session:
        _, config = active_config(session)
        if not config.run_enabled:
            return
        now = time.time()
        for window in WINDOWS:
            result = snapshot(session, window, now)
            if window == "24h":
                evaluate_alerts(session, result)


async def run(settings: Settings):
    db, vault = Database(settings.database_path), Vault(settings.secrets_dir)
    owner = str(uuid.uuid4())
    telegram = Telegram(db, vault)
    lock = (settings.data_dir / "worker.lock").open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("Ya existe un worker activo")

    async def telegram_loop():
        while True:
            try:
                await telegram.poll()
            except Exception:
                log.warning("telegram_poll_failed")
            await asyncio.sleep(3)

    async def pulse_loop():
        while True:
            try:
                await asyncio.to_thread(schedule, db)
            except Exception:
                log.warning("scheduler_cycle_failed")
            await asyncio.sleep(15)

    async def lease_loop(job_id):
        while True:
            await asyncio.sleep(30)
            await asyncio.to_thread(renew, db, job_id, owner)

    tasks = [asyncio.create_task(telegram_loop()), asyncio.create_task(pulse_loop())]
    last_score = 0.0
    try:
        while True:
            job = await asyncio.to_thread(claim, db, owner)
            if job:
                lease = asyncio.create_task(lease_loop(job.id))
                try:
                    result = await asyncio.to_thread(execute_job, db, vault, settings, job)
                    if job.kind == "telegram_query":
                        answer = (
                            result["answer"]
                            + "\n"
                            + "\n".join(d["url"] for d in result["evidence"][:5])
                        )
                        await telegram.call(
                            "sendMessage",
                            {"chat_id": job.payload["chat_id"], "text": answer[:4000]},
                        )
                    await asyncio.to_thread(finish, db, job.id, owner, result)
                    if job.kind == "poll":
                        last_score = 0
                except Exception as exc:
                    code = getattr(exc, "code", "job_failed")
                    await asyncio.to_thread(finish, db, job.id, owner, error=code)
                    log.warning("job_failed id=%s code=%s", job.id, code)
                finally:
                    lease.cancel()
            if time.time() - last_score >= 300:
                await asyncio.to_thread(recalculate, db)
                last_score = time.time()
            try:
                await deliver_notifications(db, telegram, settings)
                await deliver_health(db, telegram, settings)
            except Exception:
                log.warning("notification_cycle_failed")
            await asyncio.sleep(1 if job else 3)
    finally:
        for task in tasks:
            task.cancel()
        lock.close()
