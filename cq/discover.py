"""Route discovery for phase 1.

Probes a short, curated list of plausible routes and prints a compact
one-line summary per route so the shape of the API is visible at a glance.
The list is deliberately small (not a brute force): the run log is read by
humans and the brief warns against attacking the platform.

    python -m cq.discover            # root first, then the candidate list
    python -m cq.discover /s1/foo    # probe specific paths only
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor

from .cli import clock_guard
from .client import Client, Result

CANDIDATES = [
    "/", "/s1", "/s1/", "/s1/me", "/s1/status", "/s1/run", "/s1/help",
    "/s1/docs", "/s1/openapi.json", "/s1/briefs", "/s1/brief", "/s1/queue",
    "/s1/briefs/bf-0001", "/s1/campaigns", "/s1/campaign", "/s1/ads",
    "/s1/adgroups", "/s1/accounts", "/s1/audiences", "/s1/creatives",
    "/s1/budgets", "/s1/report", "/s1/reports", "/s1/score", "/s1/log",
    "/s1/events", "/s1/health", "/api", "/api/s1", "/s1/v1",
]


def summarize(path: str, r: Result) -> str:
    ct = r.headers.get("Content-Type", "").split(";")[0] if r.headers else ""
    body = r.text.replace("\n", " ").strip()
    j = r.json
    if isinstance(j, dict):
        keys = ",".join(list(j.keys())[:8])
        body = f"keys[{keys}] " + body
    elif isinstance(j, list):
        body = f"list[{len(j)}] " + body
    mr = r.minutes_remaining()
    tail = f"  ⏱{mr:.1f}m" if mr is not None else ""
    err = f" ERR {r.error}" if r.error else ""
    return f"{r.status:>3} {ct:16} {path:24} {body[:110]}{err}{tail}"


def probe(c: Client, path: str) -> tuple[str, Result]:
    return path, c.get(path, retry=False, tag="discover")


def main(argv: list[str]) -> int:
    clock_guard()
    c = Client()
    paths = argv or CANDIDATES
    # Root first, alone: it may describe the API and make guessing moot.
    if not argv:
        p, r = probe(c, "/s1")
        print(summarize(p, r))
        print("--- full body of /s1 ---")
        print(json.dumps(r.json, indent=2) if r.json is not None else r.text)
        print("--- candidates ---")
        paths = [x for x in paths if x != "/s1"]
    with ThreadPoolExecutor(max_workers=4) as ex:
        for p, r in ex.map(lambda x: probe(c, x), paths):
            print(summarize(p, r))
    if c.last_minutes_remaining is not None:
        print(f"[run_minutes_remaining={c.last_minutes_remaining}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
