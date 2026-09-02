# Run plan for screen 1 ("the queue")

Status: **Phase 0 complete. Clock NOT started.** No authenticated request
has been sent. `logs/` and `state/` are empty on purpose.

Goal: end with a true statement about all 240 briefs, as many as possible
genuinely built, and one sealed report posted before two hours elapse.

## Phase 0 — tooling (done)
Repo, `cq/client.py`, `cq/state.py`, `cq/run.py` scaffold, `cq/cli.py`
with clock and report guards, NOTES.md skeleton, 14 tests in `.venv`.

## Phase 1 — discovery (~15 min from clock start)
First authenticated request starts the clock:

    CQ_START_CLOCK=1 .venv/bin/python -m cq.cli probe GET /s1

Then `CQ_START_CLOCK=1 .venv/bin/python -m cq.discover` probes /s1 first, then
~30 curated routes, one summary line each. Read every
response body, errors included; the errors are the documentation.
Output: brief shape, how to create a campaign, how to read one back, what
a refusal looks like. Fill in the three stub hooks in `cq/run.py`
(`fetch_briefs`, `build_brief`, `verify_campaign`). Commit.

## Phase 2 — first full pass (~20 min)
Fetch all 240 briefs into `state/briefs.json`, attempt each with modest
concurrency. Bucket every response:
- built      – platform returned a campaign id (not yet trusted)
- transient  – refusal reads as "not right now" (rate limit, window,
               dependency not ready, 5xx) → requeue
- blocked    – refusal reads as "never" (policy, invalid brief) → keep the
               platform's own wording as the reason
- unknown    – can't tell → inspect by hand
Read a sample of real refusals BEFORE trusting the word lists in
`cq/run.py`; they are placeholders.

## Phase 3 — verification (~15 min, repeated after every retry pass)
Read back every campaign the platform said it built. Only a successful
read-back earns `built` in the report. "Built" but missing on read-back
→ reported blocked with that reason (−3 trap). Check for partial builds
(missing ads, paused) and whether the platform counts them.

## Phase 4 — retry loop (until ~1h40m)
Retry transient/unknown briefs on a schedule; verify after each pass.
Refused-then-built is +2. Probe whether some permanent-looking refusals
are fixable by adjusting the field the error complains about, without
inventing content the brief did not ask for.

## Phase 5 — report (by ~1h50m)
    .venv/bin/python -m cq.cli report              # dry run, check 240 ids
    .venv/bin/python -m cq.cli report --post --yes # seals the run
Built only if verified; everything else blocked with the platform's
reason. Ten minutes of buffer.

## Phase 6 — hand-off (after the seal)
Fill in NOTES.md (routes, refusal classes, decisions, what to fix with
more time, open doubts). Copy the untouched Claude Code transcript from
`~/.claude/projects/-Users-Yash-Developer-characterquilt-challenge-1/`
into `transcript/`. Commit.

## Standing rules
- Never claim a build that was not read back.
- At the deadline, doubt → blocked (−0.25 worst case, not −3).
- Commit after each phase; dead ends stay in history.
- Trust `run_minutes_remaining` from responses over any local timer.
- Base URL https://cq-screen.bhairav.workers.dev, key in `key.txt`
  (git-ignored), sent as `X-Candidate-Key`; custom User-Agent required.

## Resuming after a restart
1. `cd ~/Developer/characterquilt-challenge-1 && .venv/bin/python -m pytest`
2. If `logs/http.jsonl` is empty the clock has not started; otherwise
   `python -m cq.cli status` shows where the run got to and
   `state/briefs.json` is the source of truth.
