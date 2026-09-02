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


# Error codes the platform actually returns on POST /s1/campaigns (422).
# Observed in phase 1; each verified against the briefs/assets/accounts data.
TRANSIENT_CODES = {
    "asset_not_live",      # creative exists but status=draft; may go live later
    "rate_limited",
}
PERMANENT_CODES = {
    "missing_asset",       # creative id not in /s1/assets at all
    "budget_below_floor",  # brief budget < account budget_floor_cents
    "archived_account",    # every brief on acct-008
    "date_inversion",      # ends_at <= starts_at
    "unknown_account",
}


def classify_refusal(r: Result) -> str:
    """Return 'transient', 'blocked' or 'unknown' for a non-2xx build response."""
    if r.error or r.status in (408, 425, 429, 500, 502, 503, 504):
        return "transient"
    j = r.json if isinstance(r.json, dict) else {}
    code = j.get("error")
    if code in TRANSIENT_CODES:
        return "transient"
    if code in PERMANENT_CODES:
        return "blocked"
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

def _paginate(c: Client, path: str) -> list[dict]:
    """GET a cursor-paginated list ({items, next_cursor, total}) to the end."""
    # Pages sometimes repeat the boundary item (25 -> "25" returns the 25th
    # again), so dedupe by id; the repeats were identical when checked.
    seen: dict[str, dict] = {}
    cursor: Optional[str] = None
    while True:
        r = c.get(path, params={"cursor": cursor} if cursor else None, tag="list")
        if not r.ok or not isinstance(r.json, dict):
            raise RuntimeError(f"list {path} failed: {r.brief()}")
        for item in r.json.get("items") or []:
            seen.setdefault(item["id"], item)
        cursor = r.json.get("next_cursor")
        if not cursor:
            break
    total = r.json.get("total")
    if isinstance(total, int) and total != len(seen):
        raise RuntimeError(f"list {path}: got {len(seen)} unique items, platform says total={total}")
    return list(seen.values())


def fetch_briefs(c: Client) -> list[dict]:
    """GET /s1/briefs, 25 per page via ?cursor=. Ids look like 'bf-0001'."""
    return _paginate(c, "/s1/briefs")


BRIEF_FIELDS = ("account_id", "name", "objective", "budget_cents", "starts_at", "ends_at", "creative_ids")


def build_brief(c: Client, brief: dict) -> Result:
    """POST /s1/campaigns with the brief's own fields, verbatim.

    201 -> created; 200 + deduplicated -> already existed (idempotent);
    422 {error, brief_id} -> refusal (seen: missing_asset, budget_below_floor).
    """
    body = {"brief_id": brief["id"], **{k: brief[k] for k in BRIEF_FIELDS if k in brief}}
    return c.post("/s1/campaigns", json_body=body, tag="build")


def fetch_campaigns(c: Client) -> dict[str, dict]:
    """Read back every campaign the platform lists, keyed by brief_id.

    GET /s1/campaigns/{id} is 404 on this platform; the list is the only
    read-back, so verification fetches it once per pass.
    """
    out: dict[str, dict] = {}
    for item in _paginate(c, "/s1/campaigns"):
        if item.get("brief_id"):
            out[item["brief_id"]] = item
    return out


def verify_campaign(c: Client, brief: dict, campaign_id: Any, listing: Optional[dict] = None) -> bool:
    """True only if the platform lists a campaign for this brief with this id."""
    listing = fetch_campaigns(c) if listing is None else listing
    item = listing.get(brief["id"])
    return bool(item) and item.get("id") == campaign_id


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
    listing = fetch_campaigns(c)
    for bid in ids:
        rec = s.data[bid]
        if verify_campaign(c, rec["brief"], rec["campaign_id"], listing):
            s.record(bid, "verified", None, verified=True)
        else:
            # Seen in phase 2: ~10% of 201s never appear in the listing; a
            # second POST (same id, 201 again, not deduplicated) makes them
            # stick. Treat as transient so the retry loop re-posts them.
            s.record(bid, "verify-failed", None, status="transient", verified=False,
                     reason="platform returned 201 but campaign not in GET /s1/campaigns")
    s.save()
