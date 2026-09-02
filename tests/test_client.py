import json
from pathlib import Path

import requests

from cq.client import Client, RETRY_STATUSES


class FakeResponse:
    def __init__(self, status, body, headers=None):
        self.status_code = status
        self.text = body if isinstance(body, str) else json.dumps(body)
        self.headers = headers or {}


class FakeSession:
    """Scripted session: each entry is a FakeResponse or an exception."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def request(self, method, url, headers=None, json=None, params=None, timeout=None):
        self.calls.append({"method": method, "url": url, "headers": headers, "json": json, "params": params})
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make(tmp_path, script, **kw):
    sleeps = []
    session = FakeSession(script)
    c = Client(key="k-test", log_path=tmp_path / "http.jsonl", session=session,
               sleep=sleeps.append, **kw)
    c._token, c._token_exp = "tok-test", 1e12  # pre-authenticated
    return c, session, sleeps


def test_auth_is_fetched_lazily_and_refreshed_on_401(tmp_path):
    c, session, _ = make(tmp_path, [
        FakeResponse(200, {"access_token": "t1", "expires_in": 300}),
        FakeResponse(200, {"ok": 1}),
        FakeResponse(401, {"error": "expired"}),
        FakeResponse(200, {"access_token": "t2", "expires_in": 300}),
        FakeResponse(200, {"ok": 2}),
    ])
    c._token = None
    assert c.get("/s1/a").json == {"ok": 1}
    assert session.calls[0]["url"].endswith("/auth/start")
    assert session.calls[1]["headers"]["Authorization"] == "Bearer t1"
    assert c.get("/s1/b").json == {"ok": 2}
    assert session.calls[4]["headers"]["Authorization"] == "Bearer t2"


def test_sends_key_and_user_agent(tmp_path):
    c, session, _ = make(tmp_path, [FakeResponse(200, {"ok": True})])
    r = c.get("/s1/whatever")
    assert r.ok and r.json == {"ok": True}
    h = session.calls[0]["headers"]
    assert h["X-Candidate-Key"] == "k-test"
    ua = h["User-Agent"].lower()
    assert ua and "urllib" not in ua and "python" not in ua
    assert session.calls[0]["url"] == "https://cq-screen.bhairav.workers.dev/s1/whatever"


def test_logs_every_exchange_including_failures(tmp_path):
    c, _, _ = make(tmp_path, [
        requests.ConnectionError("boom"),
        FakeResponse(503, "busy"),
        FakeResponse(200, {"done": 1}),
    ])
    r = c.post("/s1/x", json_body={"a": 1})
    assert r.ok and r.attempts == 3
    lines = [json.loads(l) for l in (tmp_path / "http.jsonl").read_text().splitlines()]
    assert len(lines) == 3
    assert lines[0]["error"] and lines[0]["status"] == 0
    assert lines[1]["status"] == 503 and lines[1]["response_body"] == "busy"
    assert lines[2]["request_body"] == {"a": 1}


def test_retries_transient_and_honours_retry_after(tmp_path):
    c, _, sleeps = make(tmp_path, [
        FakeResponse(429, "slow down", {"Retry-After": "7"}),
        FakeResponse(200, {}),
    ])
    r = c.get("/s1/x")
    assert r.status == 200 and r.attempts == 2
    assert sleeps == [7.0]


def test_does_not_retry_4xx_business_errors(tmp_path):
    c, session, sleeps = make(tmp_path, [FakeResponse(422, {"error": "nope"})])
    r = c.post("/s1/x", json_body={})
    assert r.status == 422 and r.attempts == 1 and not r.ok
    assert sleeps == [] and len(session.calls) == 1


def test_gives_up_after_max_attempts(tmp_path):
    c, _, _ = make(tmp_path, [FakeResponse(500, "x")] * 3, max_attempts=3)
    r = c.get("/s1/x")
    assert r.status == 500 and r.attempts == 3


def test_tracks_minutes_remaining(tmp_path):
    c, _, _ = make(tmp_path, [FakeResponse(200, {"run_minutes_remaining": 117.5})])
    c.get("/s1/x")
    assert c.last_minutes_remaining == 117.5


def test_retry_statuses_are_transport_level_only():
    assert 429 in RETRY_STATUSES and 503 in RETRY_STATUSES
    assert 400 not in RETRY_STATUSES and 409 not in RETRY_STATUSES
