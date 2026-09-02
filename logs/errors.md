# Error digest

Generated 2026-09-02 15:07:11. 1476 exchanges logged, 703 non-2xx.

Counts are occurrences; the retry loop re-posts transient briefs every cycle, so one brief can account for many rows. 'Briefs' is the number of distinct brief ids.

| status | error | occurrences | briefs | routes |
|---|---|---|---|---|
| 422 | `asset_not_live` | 440 | 22 | POST /s1/campaigns (440) |
| 429 | `rate_limited` | 48 | 31 | POST /s1/campaigns (31), GET /s1/assets (14), GET /s1/campaigns (2) |
| 404 | `not_found` | 40 |  | GET /s1 (2), GET /s1/creatives (2), GET /s1/ (1) |
| 422 | `missing_asset` | 35 | 12 | POST /s1/campaigns (35) |
| 422 | `budget_below_floor` | 34 | 11 | POST /s1/campaigns (34) |
| 422 | `archived_account` | 33 | 11 | POST /s1/campaigns (33) |
| 422 | `date_inversion` | 33 | 11 | POST /s1/campaigns (33) |
| 401 | `missing_bearer_token` | 29 |  | GET /s1 (1), GET /s1/me (1), GET /s1/run (1) |
| 401 | `invalid_token` | 8 |  | GET /s1/assets/cr-0002 (2), GET /s1/assets (2), GET /s1/assets/cr-9072 (2) |
| 422 | `unknown_account` | 2 | 2 | POST /s1/campaigns (2) |
| 400 | `brief_id_required` | 1 |  | POST /s1/campaigns (1) |

## HTTP 422 `asset_not_live` — 440 occurrences

First seen 14:18:54, last 15:04:03.

Example: `POST /s1/campaigns`  headers {'Content-Type': 'application/json'}

Request body:
```json
{
 "brief_id": "bf-0240",
 "account_id": "acct-002",
 "name": "physio-us-northeast-leads-0240",
 "objective": "traffic",
 "budget_cents": 99000,
 "starts_at": 1769644800,
 "ends_at": 1770422400,
 "creative_ids": [
  "cr-0089"
 ]
}
```
Response body:
```json
{
  "error": "asset_not_live",
  "brief_id": "bf-0240",
  "creative_ids": [
    "cr-0089"
  ],
  "asset_status": "draft"
}
```

Briefs affected (22): bf-0003, bf-0007, bf-0015, bf-0020, bf-0022, bf-0026, bf-0028, bf-0041, bf-0057, bf-0064, bf-0084, bf-0109, bf-0123, bf-0132, bf-0147, bf-0174, bf-0179, bf-0186, bf-0188, bf-0190, bf-0236, bf-0240

## HTTP 429 `rate_limited` — 48 occurrences

First seen 14:18:56, last 15:04:12.

Example: `GET /s1/campaigns`  headers {'Content-Type': 'application/json', 'Retry-After': '8'}

Response body:
```json
{
  "error": "rate_limited"
}
```

Briefs affected (31): bf-0003, bf-0007, bf-0015, bf-0016, bf-0024, bf-0027, bf-0041, bf-0042, bf-0043, bf-0044, bf-0053, bf-0060, bf-0068, bf-0080, bf-0082, bf-0083, bf-0084, bf-0119, bf-0122, bf-0123, bf-0124, bf-0161, bf-0162, bf-0163, bf-0164, bf-0201, bf-0202, bf-0203, bf-0204, bf-0236, bf-0240

## HTTP 404 `not_found` — 40 occurrences

First seen 14:15:13, last 14:34:16.

Example: `GET /s1/assets/cr-0104?include=history`  headers {'Content-Type': 'application/json'}

Response body:
```json
{
  "error": "not_found"
}
```

## HTTP 422 `missing_asset` — 35 occurrences

First seen 14:16:34, last 15:04:11.

Example: `POST /s1/campaigns`  headers {'Content-Type': 'application/json'}

Request body:
```json
{
 "brief_id": "bf-0224",
 "account_id": "acct-003",
 "name": "childcare-us-midwest-traffic-0224",
 "objective": "conversions",
 "budget_cents": 188000,
 "starts_at": 1770076800,
 "ends_at": 1771200000,
 "creative_ids": [
  "cr-0031",
  "cr-9775"
 ]
}
```
Response body:
```json
{
  "error": "missing_asset",
  "brief_id": "bf-0224"
}
```

Briefs affected (12): bf-0002, bf-0005, bf-0008, bf-0010, bf-0024, bf-0082, bf-0111, bf-0122, bf-0189, bf-0194, bf-0207, bf-0224

## HTTP 422 `budget_below_floor` — 34 occurrences

First seen 14:16:35, last 15:04:11.

Example: `POST /s1/campaigns`  headers {'Content-Type': 'application/json'}

Request body:
```json
{
 "brief_id": "bf-0237",
 "account_id": "acct-003",
 "name": "childcare-us-midwest-awareness-0237",
 "objective": "leads",
 "budget_cents": 38000,
 "starts_at": 1768176000,
 "ends_at": 1768867200,
 "creative_ids": [
  "cr-0053"
 ]
}
```
Response body:
```json
{
  "error": "budget_below_floor",
  "brief_id": "bf-0237"
}
```

Briefs affected (11): bf-0006, bf-0053, bf-0076, bf-0090, bf-0103, bf-0112, bf-0120, bf-0183, bf-0232, bf-0234, bf-0237

## HTTP 422 `archived_account` — 33 occurrences

First seen 14:18:55, last 15:04:11.

Example: `POST /s1/campaigns`  headers {'Content-Type': 'application/json'}

Request body:
```json
{
 "brief_id": "bf-0167",
 "account_id": "acct-008",
 "name": "fitness-us-south-conversions-0167",
 "objective": "retargeting",
 "budget_cents": 241000,
 "starts_at": 1767916800,
 "ends_at": 1768780800,
 "creative_ids": [
  "cr-0060",
  "cr-0061"
 ]
}
```
Response body:
```json
{
  "error": "archived_account",
  "brief_id": "bf-0167"
}
```

Briefs affected (11): bf-0014, bf-0016, bf-0027, bf-0060, bf-0068, bf-0075, bf-0134, bf-0152, bf-0158, bf-0160, bf-0167

## HTTP 422 `date_inversion` — 33 occurrences

First seen 14:18:55, last 15:04:11.

Example: `POST /s1/campaigns`  headers {'Content-Type': 'application/json'}

Request body:
```json
{
 "brief_id": "bf-0238",
 "account_id": "acct-004",
 "name": "dental-us-west-conversions-0238",
 "objective": "conversions",
 "budget_cents": 285000,
 "starts_at": 1770508800,
 "ends_at": 1769817600,
 "creative_ids": [
  "cr-0107",
  "cr-0004"
 ]
}
```
Response body:
```json
{
  "error": "date_inversion",
  "brief_id": "bf-0238"
}
```

Briefs affected (11): bf-0029, bf-0030, bf-0054, bf-0129, bf-0137, bf-0141, bf-0200, bf-0216, bf-0228, bf-0230, bf-0238

## HTTP 401 `missing_bearer_token` — 29 occurrences

First seen 14:14:31, last 14:14:33.

Example: `GET /api`  headers {'Content-Type': 'application/json'}

Response body:
```json
{
  "error": "missing_bearer_token",
  "hint": "POST /auth/start with your X-Candidate-Key to get one"
}
```

## HTTP 401 `invalid_token` — 8 occurrences

First seen 14:16:53, last 14:16:54.

Example: `GET /s1/accounts/acct-005/creatives`  headers {'Content-Type': 'application/json'}

Response body:
```json
{
  "error": "invalid_token",
  "hint": "POST /auth/start with your X-Candidate-Key to get a fresh one"
}
```

## HTTP 422 `unknown_account` — 2 occurrences

First seen 14:16:20, last 14:16:21.

Example: `POST /s1/campaigns`  headers {'Content-Type': 'application/json'}

Request body:
```json
{
 "brief_id": "bf-0001"
}
```
Response body:
```json
{
  "error": "unknown_account",
  "brief_id": "bf-0001"
}
```

Briefs affected (2): bf-0001, bf-0002

## HTTP 400 `brief_id_required` — 1 occurrences

First seen 14:16:09, last 14:16:09.

Example: `POST /s1/campaigns`  headers {'Content-Type': 'application/json'}

Response body:
```json
{
  "error": "brief_id_required"
}
```

## Silent drops (201 returned, campaign absent from listing) — 20 briefs

No error body: the create looked successful. Detected only by reading GET /s1/campaigns back. Re-posting the same body produced 201 again and the campaign then appeared.

bf-0033, bf-0035, bf-0037, bf-0048, bf-0049, bf-0067, bf-0088, bf-0125, bf-0127, bf-0130, bf-0133, bf-0145, bf-0151, bf-0153, bf-0163, bf-0165, bf-0169, bf-0173, bf-0182, bf-0218
