# CharacterQuilt screen 1 — "the queue"

Candidate: Yashal Najeeb. Run sealed 2026-09-02 16:02 local with 13
minutes left on the platform clock.

**Result:** `POST /s1/report` → `200 {"sealed": true, "entries": 240}`.
174 briefs built and read back from the platform; 66 blocked with the
platform's own error code as the reason (22 draft assets, 11 each of
missing asset, budget below floor, archived account, date inversion).

## Read these, in order

| file | what it is |
|---|---|
| `NOTES.md` | How the platform was worked out, where it is unreliable, what I decided and why, what I would change, what I am unsure of. |
| `PLATFORM_SAYS.md` | Every refusal verbatim, and the "right now" vs "never" reading of each. |
| `API_MAP.md` | The API as reconstructed from responses: routes, shapes, validation order. |
| `report/report.final.json` | The report that was posted. `report/post_response.json` is the platform's answer. |
| `logs/errors.md` | Digest of every non-2xx response, with counts and affected briefs. |
| `logs/http.jsonl` | Every exchange with the platform, raw, one JSON line each. |
| `state/briefs.json` | Per-brief state with full attempt history. |
| `transcript/` | The untouched Claude Code session transcripts for this work. |
| `PLAN.md` | The plan written before the clock started, left as it was. |

## Reproduce the tooling

    python3 -m venv .venv && .venv/bin/pip install pytest requests
    .venv/bin/python -m pytest                       # 18 tests, no network
    .venv/bin/python scripts/error_digest.py         # regenerates logs/errors.md

The run itself cannot be repeated: the report is sealed and the key was
single-use. Code lives in `cq/` (client with bearer refresh and raw
logging, resumable state, build/verify loop, retry loop, finalize).
