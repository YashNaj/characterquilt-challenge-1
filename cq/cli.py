"""Command line entry point.

    python -m cq.cli probe GET /s1                 # raw request, prints response
    python -m cq.cli probe POST /s1/x '{"a":1}'    # with JSON body
    python -m cq.cli status                        # per-status counts from state
    python -m cq.cli report                        # print report that WOULD be sent
    python -m cq.cli report --post                 # POST /s1/report (seals the run!)

Guard: the very first authenticated request starts the two-hour clock.
The CLI refuses to send one until logs/http.jsonl exists (i.e. the clock
is already running) or CQ_START_CLOCK=1 is set in the environment.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .client import Client, HTTP_LOG
from .state import State


def clock_guard() -> None:
    if HTTP_LOG.exists() and HTTP_LOG.stat().st_size > 0:
        return
    if os.environ.get("CQ_START_CLOCK") == "1":
        return
    raise SystemExit(
        "REFUSING: no request has been sent yet, so this one would start the "
        "two-hour clock. Re-run with CQ_START_CLOCK=1 to start it deliberately."
    )


def cmd_probe(args: argparse.Namespace) -> int:
    clock_guard()
    body = json.loads(args.body) if args.body else None
    c = Client()
    r = c.request(args.method, args.path, json_body=body, retry=not args.no_retry, tag="probe")
    print(f"HTTP {r.status}  attempts={r.attempts}  {r.elapsed:.2f}s"
          + (f"  error={r.error}" if r.error else ""))
    for k, v in r.headers.items():
        if k.lower() in ("content-type", "retry-after", "x-ratelimit-remaining", "x-ratelimit-reset",
                         "link", "location") or k.lower().startswith("x-cq"):
            print(f"  {k}: {v}")
    j = r.json
    print(json.dumps(j, indent=2) if j is not None else r.text)
    if c.last_minutes_remaining is not None:
        print(f"[run_minutes_remaining={c.last_minutes_remaining}]", file=sys.stderr)
    return 0 if r.ok else 1


def cmd_status(args: argparse.Namespace) -> int:
    s = State()
    print(json.dumps(s.counts(), indent=2))
    if args.verbose:
        for bid, rec in sorted(s.data.items()):
            print(f"{bid}  {rec['status']:9} verified={rec['verified']!s:5} "
                  f"attempts={rec['attempts']:2}  {rec.get('reason') or ''}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    s = State()
    payload = s.build_report()
    counts = {}
    for v in payload["report"].values():
        counts[v["status"]] = counts.get(v["status"], 0) + 1
    print(f"report covers {len(payload['report'])} briefs: {counts}", file=sys.stderr)
    if not args.post:
        print(json.dumps(payload, indent=1))
        return 0
    if len(payload["report"]) != args.expect:
        raise SystemExit(f"REFUSING to post: report has {len(payload['report'])} briefs, expected {args.expect}")
    if not args.yes:
        raise SystemExit("REFUSING to post without --yes (this seals the run)")
    clock_guard()
    c = Client()
    r = c.post("/s1/report", json_body=payload, tag="report")
    print(r.brief(4000))
    return 0 if r.ok else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="cq")
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("probe")
    pp.add_argument("method")
    pp.add_argument("path")
    pp.add_argument("body", nargs="?")
    pp.add_argument("--no-retry", action="store_true")
    pp.set_defaults(fn=cmd_probe)

    ps = sub.add_parser("status")
    ps.add_argument("-v", "--verbose", action="store_true")
    ps.set_defaults(fn=cmd_status)

    pr = sub.add_parser("report")
    pr.add_argument("--post", action="store_true")
    pr.add_argument("--yes", action="store_true")
    pr.add_argument("--expect", type=int, default=240, help="required brief count before posting")
    pr.set_defaults(fn=cmd_report)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
