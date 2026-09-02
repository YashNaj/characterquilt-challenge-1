"""Build loop scaffold.

The platform API is undocumented, so the three hooks below are filled in
after discovery (phase 1). Everything around them -- concurrency, state,
transient/permanent classification, verification, timing -- is ready.

Flow per brief:
  pending  --build--> built (unverified) --verify--> built (verified)
           \-> transient (retry later, until the deadline)
           \-> blocked   (permanent refusal; keep the platform's reason)
"""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

from .client import Client, Result
from .state import State

# Patterns hinting a refusal is about "right now" rather than "ever".
# Populated/adjusted after reading real platform responses in phase 1.
TRANSIENT_PATTERNS = [
    r"try again", r"later", r"temporar", r"rate.?limit", r"too many",
    r"busy", r"unavailable", r"not yet", r"pending", r"in progress",
    r"timeout", r"timed out", r"maintenance", r"cooldown", r"window",
]
PERMANENT_PATTERNS = [
    r"never", r"cannot", r"not allowed", r"prohibit", r"forbidden",
    r"invalid", r"unsupported", r"policy", r"reject", r"exceeds",
]


def classify_refusal(r: Result) -> str:
    """Return 'transient' or 'blocked' for a non-2xx build response."""
    if r.error or r.status in (408, 425, 429, 500, 502, 503, 504):
        return "transient"
    text = r.text.lower()
    if any(re.search(p, text) for p in TRANSIENT_PATTERNS):
        return "transient"
    if any(re.search(p, text) for p in PERMANENT_PATTERNS):
        return "blocked"
    return "unknown"


def extract_reason(r: Result) -> str:
    j = r.json
    if isinstance(j, dict):
        for k in ("reason", "error", "message", "detail", "code"):
            v = j.get(k)
            if isinstance(v, str) and v:
                return v
            if isinstance(v, dict):
                return str(v)
    return (r.text or r.error or f"HTTP {r.status}")[:300]


# ---- hooks to fill in after discovery ---------------------------------------

def fetch_briefs(c: Client) -> list[dict]:
    """Return all 240 briefs. Each must include an 'id' like 'bf-0001'."""
    raise NotImplementedError("fill in after discovery")


def build_brief(c: Client, brief: dict) -> Result:
    """Attempt to create the campaign for one brief."""
    raise NotImplementedError("fill in after discovery")


def verify_campaign(c: Client, brief: dict, campaign_id: Any) -> bool:
    """Read the campaign back; True only if the platform says it exists."""
    raise NotImplementedError("fill in after discovery")


# ---- loop --------------------------------------------------------------------

def attempt(c: Client, s: State, bid: str) -> None:
    rec = s.ensure(bid)
    r = build_brief(c, rec["brief"])
    rec["attempts"] += 1
    if r.ok:
        j = r.json if isinstance(r.json, dict) else {}
        cid = j.get("id") or j.get("campaign_id") or (j.get("campaign") or {}).get("id")
        s.record(bid, "built", r.brief(), status="built", campaign_id=cid, verified=False, reason=None)
    else:
        kind = classify_refusal(r)
        s.record(bid, f"refused:{kind}", r.brief(), status=kind, reason=extract_reason(r))


def run_pass(c: Client, s: State, statuses=("pending", "transient", "unknown"), workers: int = 4) -> None:
    ids = [bid for st in statuses for bid, _ in s.by_status(st)]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(attempt, c, s, bid): bid for bid in ids}
        for i, f in enumerate(as_completed(futs), 1):
            f.result()
            if i % 10 == 0:
                s.save()
    s.save()


def verify_pass(c: Client, s: State, workers: int = 4) -> None:
    ids = [bid for bid, rec in s.by_status("built") if not rec["verified"]]

    def one(bid: str) -> None:
        rec = s.data[bid]
        ok = verify_campaign(c, rec["brief"], rec["campaign_id"])
        if ok:
            s.record(bid, "verified", None, verified=True)
        else:
            s.record(bid, "verify-failed", None, status="unknown", verified=False,
                     reason="platform reported built but campaign not found on read-back")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, ids))
    s.save()
