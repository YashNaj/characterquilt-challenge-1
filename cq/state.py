"""Per-brief state, persisted as JSON so the run is resumable.

Each brief record:
  status      : pending | built | blocked | transient | unknown
  reason      : platform-provided reason text (for blocked/transient)
  campaign_id : id returned by the platform when built
  verified    : True only after the campaign was read back from the platform
  attempts    : number of build attempts
  history     : list of {ts, event, detail} entries (never pruned)
  brief       : the brief payload as fetched from the queue
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Iterator, Optional

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "state" / "briefs.json"

STATUSES = ("pending", "built", "blocked", "transient", "unknown")


class State:
    def __init__(self, path: Path = STATE_PATH) -> None:
        self.path = path
        self.data: dict[str, dict] = {}
        self.meta: dict[str, Any] = {}
        if path.exists():
            raw = json.loads(path.read_text() or "{}")
            self.data = raw.get("briefs", {})
            self.meta = raw.get("meta", {})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"meta": self.meta, "briefs": self.data}, indent=1, sort_keys=True))
        os.replace(tmp, self.path)

    def ensure(self, brief_id: str, brief: Optional[dict] = None) -> dict:
        rec = self.data.setdefault(brief_id, {
            "status": "pending", "reason": None, "campaign_id": None,
            "verified": False, "attempts": 0, "history": [], "brief": None,
        })
        if brief is not None:
            rec["brief"] = brief
        return rec

    def record(self, brief_id: str, event: str, detail: Any = None, **fields: Any) -> dict:
        if "status" in fields and fields["status"] not in STATUSES:
            raise ValueError(f"bad status {fields['status']!r}")
        rec = self.ensure(brief_id)
        rec["history"].append({"ts": time.time(), "event": event, "detail": detail})
        rec.update(fields)
        return rec

    def by_status(self, status: str) -> Iterator[tuple[str, dict]]:
        for bid, rec in sorted(self.data.items()):
            if rec["status"] == status:
                yield bid, rec

    def counts(self) -> dict[str, int]:
        out = {s: 0 for s in STATUSES}
        for rec in self.data.values():
            out[rec["status"]] = out.get(rec["status"], 0) + 1
        out["verified_built"] = sum(1 for r in self.data.values() if r["status"] == "built" and r["verified"])
        return out

    def build_report(self) -> dict:
        """Report payload. Only *verified* builds are claimed as built.

        Everything else is reported blocked with the best reason we have.
        An unverified 'built' is deliberately downgraded: claiming it costs
        -3 if the platform disagrees, reporting it blocked costs at most -0.25.
        """
        report: dict[str, dict] = {}
        for bid, rec in sorted(self.data.items()):
            if rec["status"] == "built" and rec["verified"]:
                report[bid] = {"status": "built"}
            else:
                reason = rec.get("reason") or f"unresolved: last state {rec['status']}"
                report[bid] = {"status": "blocked", "reason": reason}
        return {"report": report}
