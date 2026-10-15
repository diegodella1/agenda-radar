import argparse
import asyncio
import getpass
import hashlib
import os
import sqlite3
from pathlib import Path

from .config import Settings
from .db import Database
from .editorial import initialize_config
from .security import Vault, create_user


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description="Agenda Radar")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("prepare-setup")
    sub.add_parser("doctor")
    admin = sub.add_parser("create-admin")
    admin.add_argument("--email", required=True)
    sub.add_parser("web")
    sub.add_parser("worker")
    backup = sub.add_parser("backup")
    backup.add_argument("destination", type=Path)
    restore = sub.add_parser("restore")
    restore.add_argument("source", type=Path)
    restore.add_argument("destination", type=Path)
    sub.add_parser("check")
    args = parser.parse_args()
    settings = Settings()
    db = Database(settings.database_path)
    if args.command == "init":
        db.migrate()
        Vault(settings.secrets_dir).initialize()
        with db.session() as session:
            initialize_config(session)
        print("Base migrada y almacén de secretos inicializado.")
    elif args.command == "doctor":
        import json

        from .readiness import report

        result = report(db, settings)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(0 if result["ready_for_pilot"] else 1)
    elif args.command == "prepare-setup":
        from .bootstrap import prepare

        path = prepare(db, settings.secrets_dir)
        print(f"Código de un solo uso guardado en {path} (vence en 24 horas).")
        print(f"Abrir {settings.app_base_url}/setup y leer el código localmente.")
    elif args.command == "create-admin":
        password = getpass.getpass("Contraseña (mínimo 12 caracteres): ")
        if password != getpass.getpass("Repetir contraseña: "):
            raise SystemExit("Las contraseñas no coinciden")
        with db.session() as session:
            create_user(session, args.email, password)
        print("Administrador creado.")
    elif args.command == "web":
        import uvicorn

        from .app import create_app

        uvicorn.run(
            create_app(settings),
            host=os.getenv("APP_BIND", "127.0.0.1"),
            port=int(os.getenv("APP_PORT", "8765")),
            access_log=False,
            proxy_headers=True,
            forwarded_allow_ips="127.0.0.1,::1",
        )
    elif args.command == "worker":
        from .worker import run

        asyncio.run(run(settings))
    elif args.command == "backup":
        db.backup(args.destination)
        checksum = hashlib.sha256(args.destination.read_bytes()).hexdigest()
        args.destination.with_suffix(".sha256").write_text(
            checksum + "  " + args.destination.name + "\n"
        )
        print(f"Backup verificado: {args.destination}")
    elif args.command == "restore":
        if args.destination.exists() or args.destination.resolve() == db.path:
            raise SystemExit("Restaurar en un destino nuevo, separado de la base activa")
        with sqlite3.connect(f"file:{args.source.resolve()}?mode=ro", uri=True) as source:
            if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise SystemExit("Backup inválido")
            args.destination.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(args.destination) as destination:
                source.backup(destination)
                if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise SystemExit("Restauración inválida")
        print(f"Restaurado en {args.destination}. Recuperar master.key por separado.")
    elif args.command == "check":
        with db.session() as session:
            from sqlalchemy import text

            print(session.execute(text("PRAGMA integrity_check")).scalar())


if __name__ == "__main__":
    main()
