"""Pairwise clustering evaluation on an editor-labeled corpus in an isolated database."""
import argparse
import hashlib
import itertools
import json
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

from agenda_radar.db import Database
from agenda_radar.editorial import initialize_config
from agenda_radar.ingest import store_document
from agenda_radar.models import Mention, Source
from agenda_radar.schemas import DocumentInput

parser = argparse.ArgumentParser()
parser.add_argument("corpus", type=Path)
parser.add_argument("--output", type=Path, default=Path("artifacts/corpus-evaluation.json"))
parser.add_argument("--minimum-precision", type=float, default=.9)
parser.add_argument("--minimum-recall", type=float, default=.8)
args = parser.parse_args()
raw = args.corpus.read_bytes()
records = json.loads(raw)
if len(records) < 2 or any(not r.get("expected_cluster") for r in records):
    parser.error("At least two records with expected_cluster required")
with tempfile.TemporaryDirectory(prefix="agenda-corpus-") as directory:
    db = Database(Path(directory)/"evaluation.db")
    db.migrate()
    pairs = []
    with db.session() as session:
        initialize_config(session)
        sources = {}
        for row in records:
            host = urlsplit(row["url"]).hostname
            if host not in sources:
                source = Source(name=host, url=f"https://{host}/rss", scope="reference",
                    group_name=row.get("group_name",host), legal_basis="Isolated evaluation corpus",
                    last_success=time.time(), status="healthy")
                session.add(source)
                session.flush()
                sources[host] = source
            document = store_document(session, sources[host], DocumentInput(
                title=row["title"], url=row["url"], excerpt=row.get("excerpt", ""), published_at=time.time()-60))
            session.flush()
            pairs.append((row["expected_cluster"], session.get(Mention,document.id).event_id))
    db.engine.dispose()
tp = fp = fn = 0
for a,b in itertools.combinations(pairs,2):
    expected, predicted = a[0] == b[0], a[1] == b[1]
    tp += int(expected and predicted)
    fp += int(not expected and predicted)
    fn += int(expected and not predicted)
precision = tp/(tp+fp) if tp+fp else 1.0
recall = tp/(tp+fn) if tp+fn else 1.0
result = dict(corpus_sha256=hashlib.sha256(raw).hexdigest(),documents=len(records),
    precision=precision, recall=recall, true_positive=tp, false_positive=fp, false_negative=fn,
    passed=precision>=args.minimum_precision and recall>=args.minimum_recall,
    note="Metrics apply only to this corpus; synthetic fixtures do not certify editorial quality.")
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps(result,indent=2))
raise SystemExit(0 if result["passed"] else 1)
