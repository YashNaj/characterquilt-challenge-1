# NOTES

Screen 1 ("the queue") for CharacterQuilt. Candidate: Yashal Najeeb.

## How I worked out what the platform does

Clock started 14:14 local (first request). Everything below was learned
from response bodies; there are no docs.

- Unauthenticated `GET /s1` → 401 `missing_bearer_token` with a hint:
  `POST /auth/start` with `X-Candidate-Key` returns `{access_token,
  expires_in: 300, run_minutes_remaining}`. Tokens last five minutes, so
  the client refreshes before expiry and once more on any 401 (a lock
  serialises refreshes; the first threaded run raced and produced spurious
  401s that looked like route answers).
- Live routes (everything else is 404): `GET /s1/briefs` (240),
  `GET /s1/assets` (140), `GET /s1/accounts` (8), `GET|POST /s1/campaigns`.
  `GET /s1/campaigns/{id}` is 404, so the listing is the only read-back.
- Lists are cursor-paginated 25 at a time (`?cursor=25`). Some page
  boundaries repeat the boundary item (244 rows for `total: 240`), so the
  paginator dedupes by id and checks the unique count against `total`.
- `POST /s1/campaigns` takes the brief's own fields plus `brief_id`
  (`account_id` and `creative_ids` are required; `brief_id` alone → 
  `unknown_account`). 201 on create, 200 `deduplicated: true` on repeat.
- Refusals are 422 with an `error` code and the `brief_id`:
  - `asset_not_live` (+ `creative_ids`, `asset_status: draft`) — 22 briefs.
    The creative exists but is a draft. Treated as "not right now" and
    re-posted every cycle; assets are polled to see if drafts go live.
  - `missing_asset` — 11 briefs; the creative id is not in `/s1/assets`
    at all (e.g. `cr-9072`). Permanent.
  - `budget_below_floor` — 11 briefs; `budget_cents` is under the
    account's `budget_floor_cents`. Permanent as written; raising the
    budget would change the client's brief, so not attempted.
  - `archived_account` — 11 briefs, all on `acct-008`. Permanent.
  - `date_inversion` — 11 briefs with `ends_at <= starts_at`. Permanent.
  - `rate_limited` (429, `Retry-After: 9`) — transport-level, retried.
- **The −3 trap:** in the first pass 174 POSTs returned 201 but the
  listing had `total: 154`. Twenty campaigns were accepted and silently
  dropped; nothing in their briefs distinguishes them and only 1 of 20 had
  seen a 429. Re-POSTing returns 201 again (same id, *not* deduplicated)
  and after that they appear in the listing. So every build is verified
  against the listing, dropped ones are re-posted, and the loop also
  re-verifies all previously-listed campaigns each cycle in case they
  vanish later.

## Where the platform is unreliable (measured)

From 839 logged exchanges plus targeted probes:

| Failure | Evidence | Handling |
|---|---|---|
| Creates silently dropped | 20 of 172 first-pass 201s absent from the listing (`total: 154`); 2 of 20 re-posts dropped again. No pattern in id, position, timing, content, or prior 429s. | Verify every build against the listing; re-post until listed; re-verify all each cycle. |
| Rate limiting | 429 `rate_limited`, `Retry-After` 6–9 s, arriving in bursts of four about every 10 s under 4 workers. | Honour Retry-After, back off, 3 workers in the loop. |
| Short tokens | `expires_in: 300`; concurrent refreshes raced and produced spurious 401s. | Refresh 30 s early under a lock; retry once on 401. |
| Pagination overlap | Pages repeat the boundary item at some cursors (244 rows for 240; 178 for 174). Never drops items. | Dedupe by id; assert unique count == `total`. |
| Draft assets | 22 briefs each reference exactly one `draft` creative. No timestamp, header, or route hints when/if it goes live. | Re-post every 3 min; report blocked with the code if still draft at the deadline. |

Second route sweep at 15:10 (80 more curated paths, query filters,
OPTIONS/HEAD/PATCH): nothing new. `/auth/refresh` is an alias of
`/auth/start`; `/robots.txt` is Cloudflare's default content-signal text;
every list filter (`status`, `kind`, `brief_id`, `id`) is ignored; no
method other than GET/POST on the four resources exists.

Reads are consistent: five back-to-back campaign listings were identical,
no brief drifted between fetches, latency p95 0.28 s, no 5xx seen.
GET by id does not exist for any resource.

## What I decided about the briefs I could not build

See the refusal table above. Only `asset_not_live` was retried on a
schedule (the asset can plausibly go live). The four permanent classes
are reported `blocked` with the platform's error code verbatim as the
reason. I did not edit briefs to get past `budget_below_floor` or
`date_inversion`: the brief is the client's ask, and a campaign with a
different budget or swapped dates is not the campaign they asked for.

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
- Transcript export: `scripts/export_transcript.sh` copies the raw session
  JSONL files into `transcript/` (run after the seal, then commit).


_Final read-back 2026-09-02 15:07:11: {'built': 174, 'blocked': 66}, minutes_left=68.0._
