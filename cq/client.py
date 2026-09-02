"""HTTP client for the screen platform.

Every request carries the candidate key and a User-Agent. Every exchange
(request + response, including failures) is appended verbatim to a JSONL
log so nothing is lost. Transport-level failures (429, 5xx, connection
errors) are retried with backoff and Retry-After is honoured. Business
refusals (other 4xx) are returned untouched for the caller to read.

NOTE: the *first* authenticated request starts the two-hour clock.
"""
from __future__ import annotations

import json
import os
import random
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import requests

BASE_URL = "https://cq-screen.bhairav.workers.dev"
USER_AGENT = "cq-screen-runner/0.1 (+yashalnajeeb@gmail.com)"
ROOT = Path(__file__).resolve().parent.parent
HTTP_LOG = ROOT / "logs" / "http.jsonl"

RETRY_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


def load_key() -> str:
    key = os.environ.get("CQ_KEY")
    if key:
        return key.strip()
    p = ROOT / "key.txt"
    if p.exists():
        return p.read_text().strip()
    raise SystemExit("no candidate key: set CQ_KEY or create key.txt")


@dataclass
class Result:
    status: int
    headers: dict
    text: str
    elapsed: float
    attempts: int
    error: Optional[str] = None  # transport-level error on the final attempt

    @property
    def json(self) -> Any:
        try:
            return json.loads(self.text) if self.text else None
        except json.JSONDecodeError:
            return None

    @property
    def ok(self) -> bool:
        return self.error is None and 200 <= self.status < 300

    def minutes_remaining(self) -> Optional[float]:
        body = self.json
        if isinstance(body, dict):
            v = body.get("run_minutes_remaining")
            if isinstance(v, (int, float)):
                return float(v)
        return None

    def brief(self, limit: int = 500) -> str:
        t = self.text if len(self.text) <= limit else self.text[:limit] + "…"
        err = f" error={self.error}" if self.error else ""
        return f"HTTP {self.status} ({self.attempts} attempt(s), {self.elapsed:.2f}s){err}: {t}"


class Client:
    def __init__(
        self,
        key: Optional[str] = None,
        base_url: str = BASE_URL,
        log_path: Path = HTTP_LOG,
        session: Optional[requests.Session] = None,
        max_attempts: int = 5,
        sleep: Callable[[float], None] = time.sleep,
        timeout: float = 30.0,
    ) -> None:
        self.key = key or load_key()
        self.base_url = base_url.rstrip("/")
        self.log_path = log_path
        self.session = session or requests.Session()
        self.max_attempts = max_attempts
        self.sleep = sleep
        self.timeout = timeout
        self.last_minutes_remaining: Optional[float] = None
        self._token: Optional[str] = None
        self._token_exp: float = 0.0
        self._lock = threading.Lock()

    # ---- bearer auth (discovered in phase 1) --------------------------------
    # POST /auth/start with X-Candidate-Key returns {access_token, expires_in}.
    # Tokens are short-lived (300s), so refresh a little before expiry and
    # on any 401.
    def _auth(self) -> str:
        r = self._raw("POST", f"{self.base_url}/auth/start", None, None, {}, tag="auth")
        j = r.json if isinstance(r.json, dict) else {}
        tok = j.get("access_token")
        if not tok:
            raise RuntimeError(f"auth failed: {r.brief()}")
        self._token = tok
        self._token_exp = time.time() + float(j.get("expires_in", 300)) - 30
        mr = r.minutes_remaining()
        if mr is not None:
            self.last_minutes_remaining = mr
        return tok

    def token(self) -> str:
        with self._lock:
            if self._token is None or time.time() >= self._token_exp:
                return self._auth()
            return self._token

    def _reauth_if_still(self, used: str) -> None:
        """Refresh once per stale token; concurrent threads share the refresh."""
        with self._lock:
            if self._token == used:
                self._auth()

    def _log(self, record: dict) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a") as fh:
            fh.write(json.dumps(record, default=str) + "\n")

    def request(
        self,
        method: str,
        path: str,
        json_body: Any = None,
        params: Optional[dict] = None,
        retry: bool = True,
        tag: str = "",
    ) -> Result:
        url = path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"
        attempts = 0
        reauths = 0
        while True:
            attempts += 1
            tok = self.token()
            headers = {"Authorization": f"Bearer {tok}"}
            last = self._raw(method, url, json_body, params, headers, tag, attempts)
            if last.status == 401 and reauths < 3:
                reauths += 1
                self._reauth_if_still(tok)
                continue
            mr = last.minutes_remaining()
            if mr is not None:
                self.last_minutes_remaining = mr

            retryable = last.error is not None or last.status in RETRY_STATUSES
            if not retry or not retryable or attempts >= self.max_attempts:
                return last
            self.sleep(self._backoff(attempts, last))

    def _raw(self, method: str, url: str, json_body: Any, params: Optional[dict],
             extra_headers: dict, tag: str = "", attempts: int = 1) -> Result:
        headers = {
            "X-Candidate-Key": self.key,
            "User-Agent": USER_AGENT,
            "Accept": "application/json, */*",
            **extra_headers,
        }
        if True:
            t0 = time.time()
            rec: dict = {
                "ts": t0,
                "tag": tag,
                "attempt": attempts,
                "method": method.upper(),
                "url": url,
                "params": params,
                "request_body": json_body,
            }
            try:
                resp = self.session.request(
                    method.upper(), url, headers=headers, json=json_body,
                    params=params, timeout=self.timeout,
                )
                elapsed = time.time() - t0
                last = Result(resp.status_code, dict(resp.headers), resp.text, elapsed, attempts)
                rec.update(status=resp.status_code, headers=dict(resp.headers),
                           response_body=resp.text, elapsed=elapsed)
            except requests.RequestException as exc:
                elapsed = time.time() - t0
                last = Result(0, {}, "", elapsed, attempts, error=repr(exc))
                rec.update(status=0, error=repr(exc), elapsed=elapsed)
            self._log(rec)
            return last

    @staticmethod
    def _backoff(attempt: int, last: Result) -> float:
        ra = last.headers.get("Retry-After") if last.headers else None
        if ra:
            try:
                return min(float(ra), 120.0)
            except ValueError:
                pass
        return min(2 ** attempt, 60) * (0.5 + random.random())

    def get(self, path: str, **kw: Any) -> Result:
        return self.request("GET", path, **kw)

    def post(self, path: str, json_body: Any = None, **kw: Any) -> Result:
        return self.request("POST", path, json_body=json_body, **kw)
