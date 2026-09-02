"""Readable digest of every non-2xx response in logs/http.jsonl.

    .venv/bin/python scripts/error_digest.py > logs/errors.md
"""
import collections, json, sys, time
from pathlib import Path

rows = [json.loads(l) for l in (Path(__file__).resolve().parent.parent / "logs/http.jsonl").open()]
errs = [r for r in rows if not (200 <= (r.get("status") or 0) < 300)]

def code(r):
    try:
        return json.loads(r["response_body"]).get("error")
    except Exception:
        return r.get("error") or "(non-json)"

groups = collections.defaultdict(list)
for r in errs:
    groups[(r.get("status"), code(r))].append(r)

print(f"# Error digest\n\nGenerated {time.strftime('%Y-%m-%d %H:%M:%S')}. "
      f"{len(rows)} exchanges logged, {len(errs)} non-2xx.\n")
print("Counts are occurrences; the retry loop re-posts transient briefs every cycle, "
      "so one brief can account for many rows. 'Briefs' is the number of distinct brief ids.\n")
print("| status | error | occurrences | briefs | routes |\n|---|---|---|---|---|")
for (st, cd), rs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    routes = collections.Counter(r["method"] + " " + r["url"].split("dev")[1].split("?")[0] for r in rs)
    nb = len({(r.get("request_body") or {}).get("brief_id") for r in rs} - {None})
    print(f"| {st} | `{cd}` | {len(rs)} | {nb or ''} | {', '.join(f'{k} ({v})' for k, v in routes.most_common(3))} |")

for (st, cd), rs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    r = rs[-1]
    print(f"\n## HTTP {st} `{cd}` — {len(rs)} occurrences\n")
    print(f"First seen {time.strftime('%H:%M:%S', time.localtime(rs[0]['ts']))}, "
          f"last {time.strftime('%H:%M:%S', time.localtime(r['ts']))}.")
    hdrs = {k: v for k, v in (r.get("headers") or {}).items() if k.lower() in ("retry-after", "content-type")}
    print(f"\nExample: `{r['method']} {r['url'].split('dev')[1]}`  headers {hdrs}\n")
    if r.get("request_body"):
        print("Request body:\n```json\n" + json.dumps(r["request_body"], indent=1) + "\n```")
    print("Response body:\n```json\n" + (r.get("response_body") or r.get("error") or "") + "\n```")
    briefs = sorted({(r.get("request_body") or {}).get("brief_id") for r in rs} - {None})
    if briefs:
        print(f"\nBriefs affected ({len(briefs)}): {', '.join(briefs)}")

# Silent drops: 201s whose brief later needed a re-POST are recorded in state, not the log.
st = json.loads((Path(__file__).resolve().parent.parent / "state/briefs.json").read_text())["briefs"]
dropped = sorted(b for b, rec in st.items() if any(h["event"] == "verify-failed" for h in rec["history"]))
print(f"\n## Silent drops (201 returned, campaign absent from listing) — {len(dropped)} briefs\n")
print("No error body: the create looked successful. Detected only by reading GET /s1/campaigns back. "
      "Re-posting the same body produced 201 again and the campaign then appeared.\n")
print(", ".join(dropped))
