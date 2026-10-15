"""Create an isolated, explicitly synthetic dataset. Never use the production directory."""

import json
import os
import secrets
import time
from pathlib import Path

from agenda_radar.config import Settings
from agenda_radar.db import Database
from agenda_radar.editorial import initialize_config
from agenda_radar.ingest import store_document
from agenda_radar.models import Source, State
from agenda_radar.schemas import DocumentInput
from agenda_radar.security import Vault, create_user

os.umask(0o077)
root = Path("artifacts/e2e").resolve()
if (root / "data/agenda.db").exists():
    raise SystemExit("Dataset E2E existente: elegir otro destino o conservarlo para inspección.")
settings = Settings(data_dir=root / "data", secrets_dir=root / "secrets", cookie_secure=False)
db = Database(settings.database_path)
db.migrate()
Vault(settings.secrets_dir).initialize()
password = secrets.token_urlsafe(24)
with db.session() as session:
    initialize_config(session)
    create_user(session, "demo@example.test", password)
    for index in range(5):
        source = Source(
            name=f"DEMO Medio {index + 1}",
            url=f"https://medio{index}.example/rss",
            group_name=f"DEMO Grupo {index}",
            scope="reference",
            kind="rss",
            legal_basis="Datos sintéticos de prueba",
            status="healthy",
            last_success=time.time(),
            next_poll=time.time() + 86400,
        )
        session.add(source)
        session.flush()
        for number, title in enumerate(
            [
                "Congreso aprueba presupuesto nacional para educación",
                "Municipio anuncia nuevas obras de agua potable",
                "Universidad presenta programa de becas científicas",
            ]
        ):
            if number <= index:
                store_document(
                    session,
                    source,
                    DocumentInput(
                        url=f"https://medio{index}.example/nota-{number}",
                        title="DEMO · " + title,
                        excerpt="Contenido sintético para verificar la interfaz; no es una noticia real.",
                        published_at=time.time() - 600,
                    ),
                )
    own = Source(
        name="DEMO Nuestro medio",
        url="https://propio.example/rss",
        group_name="Propio",
        scope="own",
        kind="rss",
        legal_basis="Datos sintéticos de prueba",
        status="healthy",
        last_success=time.time(),
        next_poll=time.time() + 86400,
    )
    session.add(own)
    session.flush()
    store_document(
        session,
        own,
        DocumentInput(
            url="https://propio.example/deportes",
            title="DEMO · Club barrial inaugura cancha de hockey",
            published_at=time.time() - 600,
        ),
    )
    session.add(State(key="worker_heartbeat", value={"at": time.time()}))
(root / "credentials.json").write_text(
    json.dumps({"email": "demo@example.test", "password": password})
)
print("Dataset sintético aislado creado en artifacts/e2e; credenciales en archivo privado.")
