"""Isolated local browser validation server. Never uses production data or credentials."""
import tempfile
from pathlib import Path

import uvicorn

from agenda_radar.app import create_app
from agenda_radar.config import Settings
from agenda_radar.editorial import initialize_config
from agenda_radar.security import create_user

with tempfile.TemporaryDirectory(prefix="radar-showcase-") as directory:
    root = Path(directory)
    app = create_app(Settings(_env_file=None, data_dir=root / "data",
                             secrets_dir=root / "secrets", backup_dir=root / "backups",
                             demo_dir=root / "demo", demo_corpus_dir=root / "corpus",
                             demo_enabled=True, demo_showcase=True, cookie_secure=False,
                             app_base_url="http://127.0.0.1:8879"))
    app.state.db.migrate()
    app.state.vault.initialize()
    with app.state.db.session() as session:
        initialize_config(session)
        create_user(session, "admin@example.test", "local-preview-password")
    uvicorn.run(app, host="127.0.0.1", port=8879)
