import json

import pytest

from cq.state import State


def test_roundtrip_and_history(tmp_path):
    p = tmp_path / "briefs.json"
    s = State(p)
    s.ensure("bf-0001", {"name": "x"})
    s.record("bf-0001", "attempt", {"status": 503}, status="transient", reason="platform busy")
    s.save()

    s2 = State(p)
    rec = s2.data["bf-0001"]
    assert rec["brief"] == {"name": "x"}
    assert rec["status"] == "transient" and rec["reason"] == "platform busy"
    assert rec["history"][0]["event"] == "attempt"
    assert json.loads(p.read_text())["briefs"]["bf-0001"]["status"] == "transient"


def test_rejects_unknown_status(tmp_path):
    s = State(tmp_path / "b.json")
    with pytest.raises(ValueError):
        s.record("bf-0001", "x", status="shipped")


def test_report_only_claims_verified_builds(tmp_path):
    s = State(tmp_path / "b.json")
    s.record("bf-0001", "built", status="built", campaign_id="c1", verified=True)
    s.record("bf-0002", "built", status="built", campaign_id="c2", verified=False)
    s.record("bf-0003", "refused", status="blocked", reason="budget exceeds cap")
    s.record("bf-0004", "retrying", status="transient", reason="rate limited")
    s.ensure("bf-0005")

    rep = s.build_report()["report"]
    assert rep["bf-0001"] == {"status": "built"}
    assert rep["bf-0002"]["status"] == "blocked"          # unverified => not claimed
    assert rep["bf-0003"] == {"status": "blocked", "reason": "budget exceeds cap"}
    assert rep["bf-0004"]["status"] == "blocked" and "rate limited" in rep["bf-0004"]["reason"]
    assert rep["bf-0005"]["status"] == "blocked"
    assert len(rep) == 5


def test_counts(tmp_path):
    s = State(tmp_path / "b.json")
    s.record("a", "x", status="built", verified=True)
    s.record("b", "x", status="built", verified=False)
    s.record("c", "x", status="blocked")
    c = s.counts()
    assert c["built"] == 2 and c["verified_built"] == 1 and c["blocked"] == 1
