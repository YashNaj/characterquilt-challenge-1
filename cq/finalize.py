"""End of run. Dry by default; --post seals.

    .venv/bin/python -m cq.finalize          # stop loop, final read-back, write report draft, digest, commit
    .venv/bin/python -m cq.finalize --post   # all of the above, then POST /s1/report (ONE SHOT)

Steps:
  1. Stop the retry loop (state/loop.pid) so nothing writes state concurrently.
  2. Final read-back: every 'built' brief must be in GET /s1/campaigns with
     its id, or it is downgraded and reported blocked.
  3. Write report/report.final.json (exactly what would be / was posted).
  4. Regenerate logs/errors.md, stamp NOTES.md, commit.
  5. --post only: POST the report, save the platform's answer to
     report/post_response.json, commit again.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .client import Client
from .loop import reverify_all
from .run import verify_pass
from .state import State

ROOT = Path(__file__).resolve().parent.parent


def stop_loop() -> str:
    pidf = ROOT / "state/loop.pid"
    if not pidf.exists():
        return "no pid file"
    pid = int(pidf.read_text().strip() or 0)
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(50):
            time.sleep(0.1)
            os.kill(pid, 0)
        return f"pid {pid} did not exit"
    except ProcessLookupError:
        return f"pid {pid} stopped"


def sh(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", action="store_true")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()

    print("1. loop:", stop_loop())
    c = Client()
    s = State()
    lost = reverify_all(c, s)
    verify_pass(c, s)  # anything downgraded above is now 'transient' unverified -> stays blocked in report
    counts = s.counts()
    print(f"2. read-back: lost={lost} counts={counts} minutes_left={c.last_minutes_remaining}")

    payload = s.build_report()
    n = len(payload["report"])
    tally = {}
    for v in payload["report"].values():
        tally[v["status"]] = tally.get(v["status"], 0) + 1
    (ROOT / "report").mkdir(exist_ok=True)
    (ROOT / "report/report.final.json").write_text(json.dumps(payload, indent=1))
    print(f"3. report/report.final.json: {n} briefs {tally}")
    if n != 240:
        print("REFUSING: report does not cover 240 briefs", file=sys.stderr)
        return 2

    sh(".venv/bin/python", "scripts/error_digest.py")
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    notes = ROOT / "NOTES.md"
    notes.write_text(notes.read_text() + f"\n\n_Final read-back {stamp}: {tally}, minutes_left={c.last_minutes_remaining}._\n")
    sh("git", "add", "-A")
    sh("git", "commit", "-qm", f"Finalize ({'POST' if a.post else 'dry run'}) {stamp}: {tally}")
    print("4. committed")

    if not a.post:
        print("dry run only; nothing posted")
        return 0
    if not a.yes:
        print("REFUSING to post without --yes", file=sys.stderr)
        return 2
    r = c.post("/s1/report", json_body=payload, tag="report")
    (ROOT / "report/post_response.json").write_text(json.dumps(
        {"status": r.status, "headers": r.headers, "body": r.text, "attempts": r.attempts}, indent=1))
    print("5. POST /s1/report ->", r.brief(2000))
    sh("git", "add", "-A")
    sh("git", "commit", "-qm", f"Posted report {stamp}: HTTP {r.status}")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
