import sqlite3

from agenda_radar.db import Database
from agenda_radar.jobs import claim, enqueue, finish
from agenda_radar.models import User


def test_migrations_fts_backup(tmp_path):
    db = Database(tmp_path / "test.db")
    db.migrate()
    with db.engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert connection.exec_driver_sql("SELECT count(*) FROM document_fts").scalar() == 0
    with db.session() as session:
        session.add(User(email="'; DROP TABLE users;--", password_hash="hash", role="reader"))
    backup = tmp_path / "backup.db"
    db.backup(backup)
    with sqlite3.connect(backup) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT count(*) FROM users").fetchone()[0] == 1
    db.migrate("base")
    db.migrate()


def test_job_lease_and_idempotency(tmp_path):
    db = Database(tmp_path / "jobs.db")
    db.migrate()
    first = enqueue(db, "poll", {"source_id": 1}, "poll:1")
    assert enqueue(db, "poll", {"source_id": 1}, "poll:1") == first
    job = claim(db, "worker-a", now=100, lease_seconds=5)
    # Jobs are scheduled against wall-clock time unless explicitly scheduled.
    assert job is None
    import time

    now = time.time()
    job = claim(db, "worker-a", now=now)
    assert job is not None
    assert claim(db, "worker-b", now=now) is None
    recovered = claim(db, "worker-b", now=now + 301)
    assert recovered is not None and recovered.id == first
    assert not finish(db, first, "worker-a")
    assert finish(db, first, "worker-b")


def test_backup_rotation_ignores_foreign_files(tmp_path):
    from datetime import datetime, timezone

    from agenda_radar.maintenance import rotate_backups

    start = datetime(2026, 10, 15, tzinfo=timezone.utc).timestamp()
    for day in range(60):
        path = tmp_path / f"agenda-{int((start - day * 86400) * 1_000_000_000)}.db"
        path.write_bytes(b"fixture")
        path.with_suffix(".sha256").write_text("fixture")
    foreign = tmp_path / "manual-backup.db"
    foreign.write_bytes(b"keep")
    keep = rotate_backups(tmp_path)
    assert 7 <= keep <= 11
    assert foreign.read_bytes() == b"keep"
