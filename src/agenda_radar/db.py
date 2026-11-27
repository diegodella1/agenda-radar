import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session


class Database:
    def __init__(self, path: Path, *, durable: bool = True):
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.engine = create_engine(f"sqlite:///{self.path}", connect_args={"timeout": 5})

        @event.listens_for(self.engine, "connect")
        def pragmas(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=5000")
            connection.execute("PRAGMA synchronous=FULL" if durable else "PRAGMA synchronous=NORMAL")
            os.chmod(self.path, 0o600)

    @contextmanager
    def session(self):
        with Session(self.engine, expire_on_commit=False) as session:
            try:
                yield session
                session.commit()
            except BaseException:
                session.rollback()
                raise

    def migrate(self, revision="head"):
        root = Path(__file__).resolve().parent
        config = Config()
        config.set_main_option("script_location", str(root / "migrations"))
        with self.engine.begin() as connection:
            config.attributes["connection"] = connection
            if revision == "base":
                command.downgrade(config, revision)
            else:
                command.upgrade(config, revision)

    def backup(self, destination: Path):
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if destination.exists():
            raise ValueError("El destino ya existe")
        with sqlite3.connect(self.path) as source, sqlite3.connect(destination) as target:
            source.backup(target)
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Backup inválido")
        os.chmod(destination, 0o600)
