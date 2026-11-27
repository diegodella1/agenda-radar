"""Serve an isolated offline fixture for browser tests; never reads production settings."""

import argparse
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from demo_helpers import prepare_corpus  # noqa: E402

from agenda_radar.app import create_app  # noqa: E402
from agenda_radar.config import Settings  # noqa: E402
from agenda_radar.editorial import initialize_config  # noqa: E402
from agenda_radar.security import create_user  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--port', type=int, default=8791)
args = parser.parse_args()
with TemporaryDirectory(prefix='radar-performance-') as directory:
    root = Path(directory)
    prepare_corpus(root / 'corpus')
    app = create_app(Settings(
        _env_file=None, data_dir=root / 'data', secrets_dir=root / 'secrets',
        demo_dir=root / 'demo', demo_corpus_dir=root / 'corpus', backup_dir=root / 'backups',
        cookie_secure=False, demo_enabled=True,
    ))
    app.state.db.migrate()
    app.state.vault.initialize()
    with app.state.db.session() as session:
        initialize_config(session)
        create_user(session, 'admin@example.test', 'performance-test-password')
    try:
        uvicorn.run(app, host='127.0.0.1', port=args.port)
    finally:
        app.state.db.engine.dispose()
