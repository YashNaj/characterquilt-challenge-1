# API map, reconstructed from responses

No documentation exists on the platform (no WADL, OpenAPI, index, links or
`Allow` headers). Everything below was inferred from ~1,300 logged
exchanges. Verbatim bodies are in `PLATFORM_SAYS.md`; the raw log is
`logs/http.jsonl`.

```text
https://cq-screen.bhairav.workers.dev
│
├── GET  /            {"service":"cq-screen","ok":true}
├── GET  /health      same body
├── GET  /robots.txt  Cloudflare boilerplate
│
├── /auth
│   ├── POST|GET /auth/start     X-Candidate-Key → {access_token, expires_in:300, run_minutes_remaining}
│   └── POST|GET /auth/refresh   alias of /auth/start
│
└── /s1                          all require  Authorization: Bearer <access_token>
    ├── GET  /s1/briefs          paginated list, 240
    ├── GET  /s1/assets          paginated list, 140
    ├── GET  /s1/accounts        flat list, 8 (no pagination fields)
    ├── GET  /s1/campaigns       paginated list of what has actually been created
    ├── POST /s1/campaigns       create one campaign for one brief
    └── POST /s1/report          seal the run (never called; shape from the email)
```

Everything else is `404 {"error":"not_found"}`: per-item GETs
(`/s1/briefs/bf-0001`, `/s1/campaigns/cmp-0001`, `/s1/assets/cr-0001`,
`/s1/accounts/acct-001`), nested paths, OPTIONS/HEAD/PATCH/DELETE, and
~140 other guessed names.

## Auth

| step | request | response | notes |
|---|---|---|---|
| no token | any `/s1/*` | `401 {"error":"missing_bearer_token","hint":"POST /auth/start with your X-Candidate-Key to get one"}` | the only route the platform ever names |
| get token | `POST /auth/start` + `X-Candidate-Key` | `200 {"access_token","expires_in":300,"run_minutes_remaining"}` | the first call starts the two-hour clock; the only place the clock is reported |
| stale token | any `/s1/*` | `401 {"error":"invalid_token","hint":"POST /auth/start ... to get a fresh one"}` | tokens last 5 min; issuing a new one does not seem to revoke the old |

## Lists

All three paginated lists share one envelope and one bug:

```text
{"items": [...], "next_cursor": "25" | null, "total": 240}
```

- Page size 25, `?cursor=<offset>`; `limit`, `page`, `offset` and every
  filter (`status`, `kind`, `id`, `brief_id`, `include`) are ignored.
- Some cursors are inclusive of the previous boundary item (cursor 25 can
  return items 25–50, 26 rows). Dedupe by id; unique count always equals
  `total`. Nothing is ever skipped (verified with an overlapping walk at
  every offset of 10).
- Past the end (`cursor` ≥ total) returns the last item alone; negative
  returns an empty page.

### Resource shapes

```text
brief    {id: "bf-0001", account_id, name, objective, budget_cents, starts_at, ends_at, creative_ids: [cr-…]}
asset    {id: "cr-0001", kind: carousel|image|video, ratio: 1:1|16:9|9:16|4:5, status: live|draft}
account  {id: "acct-001", name, budget_floor_cents}          ← no status field, yet one account is archived
campaign {id: "cmp-0001", brief_id, account_id, created_at}  ← none of the posted fields are echoed
```

Objectives seen: awareness, traffic, leads, conversions, retargeting.
Brief ids bf-0001…bf-0240 and asset ids cr-0001…cr-0140 are contiguous.

## POST /s1/campaigns

Body = the brief's fields plus `brief_id`. Validation is on the **posted
body**, not the stored brief (a body without `creative_ids` is refused
even though the brief has them). The order the checks run in, inferred
from which error wins when several apply:

```text
POST /s1/campaigns
 │
 ├─ no brief_id            → 400 brief_id_required
 ├─ no/unknown account_id  → 422 unknown_account
 ├─ account archived       → 422 archived_account        (acct-008)
 ├─ creative id not found  → 422 missing_asset           (also when creative_ids absent)
 ├─ creative status≠live   → 422 asset_not_live  + {creative_ids, asset_status:"draft"}
 ├─ budget < account floor → 422 budget_below_floor
 ├─ ends_at ≤ starts_at    → 422 date_inversion
 ├─ too fast               → 429 rate_limited   Retry-After: 6–9  (bursts of 4 per ~10 s at 4 workers)
 ├─ brief already built    → 200 {…, "deduplicated": true}   (idempotent on brief_id)
 └─ ok                     → 201 {id, brief_id, account_id, created_at}
                                  ⚠ ~1 in 8 of these is never persisted. Same body again → 201
                                    again (same id, no deduplicated flag) and then it persists.
```

Every 422 carries `brief_id`; only `asset_not_live` carries anything
else. No refusal carries `Retry-After`.

## What the errors say about data you cannot otherwise see

| error | reveals | visible elsewhere? |
|---|---|---|
| `archived_account` | acct-008 is archived | no — accounts list has no status |
| `budget_below_floor` | floor is enforced per account | yes — `budget_floor_cents` |
| `missing_asset` | ids must exist in `/s1/assets` | yes — cr-9xxx never listed |
| `asset_not_live` | assets have a lifecycle; only `live` is usable | yes — `status` field |
| 201 vs listing | writes are unreliable | only by reading `/s1/campaigns` back |
| `run_minutes_remaining` | the clock | only in the auth response |

## Read-back

`GET /s1/campaigns` is the single source of truth for "built". It was
identical across five consecutive reads, contains at most one campaign per
`brief_id`, and its `total` matched the unique count every time.

## POST /s1/report (untested)

```json
{"report": {"bf-0001": {"status": "built"},
            "bf-0002": {"status": "blocked", "reason": "<why>"}}}
```

Shape from the email. Seals the run; one shot. `GET`, `HEAD`, `OPTIONS`
and `?dry_run=1` on it are 404, so there is no preview.
