"""Phase 4 retry loop: poll until the deadline, re-posting transient briefs.

Each cycle:
  1. Re-verify EVERY campaign we believe is built against GET /s1/campaigns
     (phase 2 showed 201s that never persisted; assume they can also vanish).
  2. Re-POST every transient brief (asset_not_live, dropped 201s), verify.
  3. Log the asset status counts so we can see drafts going live.
Stops when run_minutes_remaining (from /auth/start) drops below --stop-at.

    .venv/bin/python -m cq.loop --every 180 --stop-at 25
"""
from __future__ import annotations

import argparse
import collections
import json
import time

from .client import Client
from .run import _paginate, fetch_campaigns, run_pass, verify_pass
from .state import State


def reverify_all(c: Client, s: State) -> int:
    listing = fetch_campaigns(c)
    lost = 0
    for bid, rec in list(s.by_status("built")):
        item = listing.get(bid)
        if not item or item.get("id") != rec["campaign_id"]:
            lost += 1
            s.record(bid, "vanished", json.dumps(item), status="transient", verified=False,
                     reason="campaign previously listed is no longer in GET /s1/campaigns")
    s.save()
    return lost


def cycle(c: Client, s: State) -> dict:
    lost = reverify_all(c, s)
    # Blocked briefs are re-posted unchanged too: it costs 44 requests per
    # cycle and is the only way to notice if the platform's world changes
    # (an account un-archived, a floor lowered, an asset appearing).
    before = {bid: rec["reason"] for bid, rec in s.by_status("blocked")}
    run_pass(c, s, statuses=("transient", "unknown", "blocked"), workers=3)
    verify_pass(c, s)
    changed = {bid: (before[bid], s.data[bid]["status"], s.data[bid]["reason"])
               for bid in before if s.data[bid]["status"] != "blocked" or s.data[bid]["reason"] != before[bid]}
    if changed:
        print("BLOCKED CHANGED:", json.dumps(changed), flush=True)
    assets = collections.Counter(a["status"] for a in _paginate(c, "/s1/assets"))
    return {"lost": lost, "assets": dict(assets), **s.counts()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=int, default=180)
    ap.add_argument("--stop-at", type=float, default=25.0, help="stop when this many minutes remain")
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    c = Client()
    s = State()
    from pathlib import Path
    import os
    Path("state/loop.pid").write_text(str(os.getpid()))
    while True:
        c._auth()  # refresh clock reading
        left = c.last_minutes_remaining
        info = cycle(c, s)
        print(time.strftime("%H:%M:%S"), f"left={left}", json.dumps(info), flush=True)
        if a.once or (left is not None and left <= a.stop_at):
            return 0
        time.sleep(a.every)


if __name__ == "__main__":
    raise SystemExit(main())
