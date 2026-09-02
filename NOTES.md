# NOTES

Screen 1 ("the queue") for CharacterQuilt. Candidate: Yashal Najeeb.

## How I worked out what the platform does

_(filled in during the run: routes found, what each error told me, the
transient-vs-permanent distinction as the platform actually expresses it)_

## What I decided about the briefs I could not build

_(per refusal class: what the platform said, whether I retried, why I
reported it the way I did)_

## Scoring stance

- A brief is reported `built` only if it was read back from the platform
  after creation. A build response alone is not enough (−3 if wrong).
- Refusals that read as "not right now" are retried until late in the run
  (+2 if they land). Refusals that read as "never" are reported blocked
  with the platform's own reason.
- Unresolved briefs at the deadline are reported blocked, not built
  (−0.25 worst case vs −3).

## What I would fix with another two hours

_(tbd)_

## What I am still unsure of

_(tbd)_

## Tooling

- `cq/client.py` – authenticated client; retries transport failures; logs
  every exchange to `logs/http.jsonl` (raw, untidied).
- `cq/state.py` – per-brief state in `state/briefs.json`, resumable.
- `cq/run.py` – build/verify loop; hooks filled in after discovery.
- `cq/cli.py` – `probe`, `status`, `report [--post --yes]`.
- `cq/discover.py` – one-shot probe of ~30 curated routes for phase 1.
- Tests: `.venv/bin/python -m pytest`.
- Clock guard: the CLI refuses the first authenticated request unless
  `CQ_START_CLOCK=1` is set.
- Agent transcript: Claude Code session stored under
  `~/.claude/projects/-Users-Yash-Developer-characterquilt-challenge-1/`;
  copy the session `.jsonl` into `transcript/` before sending.
