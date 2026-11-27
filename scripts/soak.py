"""Observe HTTP readiness for a bounded period; never fabricate an elapsed pilot."""
import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--hours", type=float, default=24)
parser.add_argument("--interval", type=float, default=60)
parser.add_argument("--url", default="https://aradar.diegodella.ar/health/ready")
parser.add_argument("--output", default="artifacts/soak")
args = parser.parse_args()
if args.hours <= 0 or args.interval < 1:
    parser.error("hours > 0, interval >= 1")
folder = Path(args.output)
folder.mkdir(parents=True, exist_ok=True)
started = time.time()
state = dict(started_at=started, duration_hours=args.hours, url=args.url,
             samples=0, failures=0, status="running", passed=False, scope="HTTP availability only; not editorial acceptance")
while True:
    sample = {"at": time.time()}
    begin = time.monotonic()
    try:
        with urllib.request.urlopen(urllib.request.Request(args.url, headers={"User-Agent": "AgendaRadar-Health/1.0"}), timeout=10) as response:
            sample["ok"] = response.status == 200 and json.load(response).get("status") == "ready"
    except urllib.error.HTTPError as error:
        sample.update(ok=False, error="HTTPError", status_code=error.code)
    except Exception as error:
        sample.update(ok=False, error=type(error).__name__)
    sample["latency_ms"] = round((time.monotonic()-begin)*1000, 2)
    state["samples"] += 1
    state["failures"] += int(not sample["ok"])
    state["last_sample"] = sample
    state["elapsed_seconds"] = time.time()-started
    if state["elapsed_seconds"] >= args.hours*3600:
        state.update(status="completed", passed=state["failures"] == 0)
    with (folder/"samples.jsonl").open("a") as file:
        file.write(json.dumps(sample)+"\n")
    temporary = folder/"status.tmp"
    temporary.write_text(json.dumps(state, indent=2)+"\n")
    temporary.replace(folder/"status.json")
    if state["status"] == "completed":
        raise SystemExit(0 if state["passed"] else 1)
    time.sleep(min(args.interval, max(0, args.hours*3600-state["elapsed_seconds"])))
