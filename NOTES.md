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

From roughly 3,100 logged exchanges plus targeted probes:

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

## Scoring stance

- A brief is reported `built` only if it was read back from the platform
  after creation. A build response alone is not enough (−3 if wrong).
- Refusals that read as "not right now" are retried until late in the run
  (+2 if they land). Refusals that read as "never" are reported blocked
  with the platform's own reason.
- Unresolved briefs at the deadline are reported blocked, not built
  (−0.25 worst case vs −3).

## What I decided about the briefs I could not build

The 44 briefs I reported blocked were refused for reasons fixed in the
data the platform holds, not in anything I controlled: eleven referenced
a creative id that does not exist, eleven had a budget under their
account's floor, eleven were on the one archived account, and eleven had
an end date before their start date.
The dates and budgets are properties of the brief, checked against the
account; the archived state belongs to the account. I did not
change budgets, dates, accounts or creative lists to force them through,
because the brief is the client's ask and a campaign built to different
numbers is not the campaign they asked for. All 44 were re-posted
unchanged every three minutes for the rest of the run and refused
identically each time.

The other 22 were refused because their single creative was still a
draft. That is a state, not an identity, so I treated it as "not yet"
and ran a loop for about 90 minutes that re-posted them, re-verified
every existing build against the listing, and watched the asset list.
No asset changed status during the run, so they are reported blocked
with the platform's code and the creative id.

## What I would do differently

Not much. The buildable and blocked sets were identified inside the
first fifteen minutes; everything after that was verification. The one
thing I would extend is the loop: the only state on this platform that
looked mutable was `live | draft` on assets, and I only observed it for
ninety minutes. Given another two hours I would simply keep the loop
running and post at the end.

## What I am still unsure of

- The exact shape of the API beyond what I could provoke. There is no
  description document, no links in responses, and routes were found by
  guessing nouns, so a route with a name I never tried would be invisible.
- Whether the draft assets were ever going to go live inside the two
  hours, or whether that class was a permanent refusal wearing a
  transient costume.
- The order of validation in `POST /s1/campaigns` is inferred from which
  error wins, not documented.

## Tooling

All in `cq/`: `client.py` (bearer refresh under a lock, Retry-After
backoff, every exchange appended raw to `logs/http.jsonl`), `state.py`
(per-brief state and history, report builder that only claims verified
builds), `run.py` (fetch, build, verify against the listing),
`loop.py` (re-verify all, re-post transient and blocked, watch assets),
`finalize.py` (final read-back, report file, one-shot post).
`.venv/bin/python -m pytest` runs 18 offline tests.

_Final read-back 2026-09-02 16:02:22: {'built': 174, 'blocked': 66}, minutes_left=13.0._

_Transcript note: `transcript/` is the raw Claude Code session record,
copied untouched. The candidate key value appears in the phase-0 session
(when `key.txt` was written). It is a single-use key for this one sealed
test run and is left as-is deliberately; nothing in the transcript was
edited._
