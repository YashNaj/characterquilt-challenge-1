# What the platform is telling me

Every response body below is copied verbatim from `logs/http.jsonl`
(regenerate the extraction with `scripts/error_digest.py`). For each
message: what it literally says, what it refers to when cross-checked
against `/s1/briefs`, `/s1/assets` and `/s1/accounts`, and whether it is a
fact about the world or about the world *right now*. The test for
"right now" is simple: does the message name a *state* that can change,
or an *identity/existence* that cannot?

## 1. Refusals that describe a state → "right now" → retried

### `asset_not_live` (22 briefs)

```json
{"error": "asset_not_live", "brief_id": "bf-0003",
 "creative_ids": ["cr-0104"], "asset_status": "draft"}
```

Literally: the asset exists, and its status is `draft`, not `live`. The
platform volunteers the status field, which it does not do for any other
refusal. `GET /s1/assets` confirms `cr-0104` exists with `"status": "draft"`.
A status is a state; states change. This is the platform saying "not
yet", so each of the 22 briefs is re-posted every three minutes and would
be reported `built` the moment a re-post lands and is read back.
As of 14:46 (74 minutes in) no draft asset has changed status.

### `rate_limited` (35 occurrences)

```text
{"error": "rate_limited"}      // HTTP 429, Retry-After: 9
```

Literally: too fast, come back in 9 seconds. Pure "right now"; the client
waits and retries the same request. Every one of these eventually
succeeded or produced one of the refusals below.

### Silent drop after `201 Created` (20 briefs)

```json
{"id": "cmp-0033", "brief_id": "bf-0033", "account_id": "acct-005",
 "created_at": 1788383935944}
```

Literally: created. But `GET /s1/campaigns` at 14:19:59 said `"total": 154`
after 174 such responses, and `cmp-0033` was not in it. The platform said
"built" and was not telling the truth. Re-posting the identical body
returned `201` again (same id, no `deduplicated` flag) and at 14:21:08 the
total was 156 and `cmp-0033` was listed. This is the "not on the first
attempt" case in its purest form: the refusal is not even a refusal. Only
the read-back distinguishes it. All 20 are now listed and verified.

## 2. Refusals that describe an identity → "never" → reported blocked

### `missing_asset` (11 briefs)

```json
{"error": "missing_asset", "brief_id": "bf-0005"}
```

Literally: an asset the brief names does not exist. Note the contrast with
`asset_not_live`: here the platform gives no `asset_status` because there
is no asset to have a status. Cross-check: every one of the 11 briefs
names exactly one id of the form `cr-9xxx`, and `/s1/assets` holds only
`cr-0001` to `cr-0140`. Existence is not a state that a wait will change.
The same code was also returned once for a probe that omitted
`creative_ids` entirely (bf-0002, later built), so it means "no usable
asset in the request", not "asset temporarily unavailable".

### `budget_below_floor` (11 briefs)

```json
{"error": "budget_below_floor", "brief_id": "bf-0006"}
```

Literally: the budget is under the account's floor. Cross-check: bf-0006
has `budget_cents: 52000`; `acct-001` has `budget_floor_cents: 58000`.
All 11 are short by 2,000 to 15,000 cents. Floors were re-read at 14:22
and 14:35 and had not moved. The only way this changes is by changing the
brief's budget, which is the client's number, not ours.

### `archived_account` (11 briefs)

```json
{"error": "archived_account", "brief_id": "bf-0014"}
```

Literally: the account is archived. All 11 are on `acct-008`
("fitness-us-midwest"), the only account with that name. "Archived" is
technically a state, but it is the account's state, not the brief's, and
nothing in the API exposes or changes it. Re-posting cannot help.

### `date_inversion` (11 briefs)

```json
{"error": "date_inversion", "brief_id": "bf-0029"}
```

Literally: the dates are the wrong way round. Cross-check: bf-0029 has
`starts_at` 2026-01-04 and `ends_at` 2025-12-27. All 11 end 1 to 9 days
before they start. That is a property of the brief as written and cannot
become true by waiting.

## 3. Messages about *us*, not about the briefs

| body | meaning | handled by |
|---|---|---|
| `{"error":"missing_bearer_token","hint":"POST /auth/start with your X-Candidate-Key to get one"}` | no token yet | auth on first use |
| `{"error":"invalid_token","hint":"POST /auth/start ... to get a fresh one"}` | token expired (300 s) or superseded | refresh under a lock, retry once |
| `{"error":"brief_id_required"}` (400) | body without `brief_id` | probe only |
| `{"error":"unknown_account","brief_id":"bf-0002"}` | body without `account_id` | probe only; bf-0002 built with full body |
| `{"error":"not_found"}` (404) | route does not exist | discovery only |
| `{"... "deduplicated": true}` (200) | this brief already has a campaign; nothing created | safe idempotent retry |

## Summary of the split

| platform says | about | verdict | briefs | report |
|---|---|---|---|---|
| `asset_not_live` + `asset_status: draft` | a state | right now | 22 | blocked unless a draft goes live before the seal |
| `201` but not in listing | a lie | right now | 20 | built (all recovered and read back) |
| `rate_limited` | our pace | right now | 0 net | n/a |
| `missing_asset` | existence | never | 11 | blocked |
| `budget_below_floor` | the brief's number | never | 11 | blocked |
| `archived_account` | the account | never | 11 | blocked |
| `date_inversion` | the brief's dates | never | 11 | blocked |

174 built and read back, 44 blocked for stated reasons, 22 waiting on a
state the platform has told us is `draft`.
