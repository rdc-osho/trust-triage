#!/usr/bin/env python3
"""Abuse report triage for a voice AI platform.

Reads user abuse reports, classifies each one, scores the risk as impact times
likelihood, routes it to the right queue and produces a trust KPI dashboard.

Classification uses the Claude API, with a simple keyword baseline as a fallback
and for comparison. Every report is routed so that the most harmful cases always
reach a person first.

All reports in reports.csv are synthetic examples. No real people are named.

How to run
  python triage.py reports.csv            uses the Claude API (key in .env)
  python triage.py reports.csv --mock     offline, keyword baseline only
"""
import argparse
import csv
import html
import json
import os
import re
import time
from collections import Counter
from pathlib import Path

# Impact of each harm type on a scale of 1 to 5
IMPACT = {
    "child_safety": 5,
    "fraud_scam": 5,
    "election_misinformation": 5,
    "non_consensual_clone": 4,
    "impersonation_public_figure": 4,
    "harassment_hate": 4,
    "spam_other": 2,
    "not_violating": 1,
}
CATEGORIES = list(IMPACT)
ALWAYS_URGENT = {"child_safety"}

KEYWORDS = {
    "child_safety": ["minor", "child"],
    "fraud_scam": ["scam", "money", "bank"],
    "election_misinformation": ["election"],
    "non_consensual_clone": ["consent"],
    "impersonation_public_figure": ["celebrity", "famous"],
    "harassment_hate": ["harass", "hate"],
    "spam_other": ["spam"],
}

PROMPT = """You triage abuse reports for a voice AI platform.
Classify the report into exactly one category from this list:
{cats}
Return ONLY a JSON object with these keys:
  category: one of the categories above
  likelihood: 1 to 5, how likely it is that real harm is happening, based only on the report
  confidence: "high", "medium" or "low"
  reason: one short sentence
Do not repeat any personal details from the report.

Report: {text}"""


def load_env(path=".env"):
    p = Path(path)
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def keyword_baseline(text):
    """Simple rule based classifier used offline and as a comparison point."""
    t = text.lower()
    for cat in ["child_safety", "election_misinformation", "fraud_scam", "non_consensual_clone",
                "impersonation_public_figure", "harassment_hate", "spam_other"]:
        if any(k in t for k in KEYWORDS[cat]):
            return {"category": cat, "likelihood": 3, "confidence": "low", "reason": "keyword match"}, 0
    return {"category": "not_violating", "likelihood": 1, "confidence": "low", "reason": "no keyword match"}, 0


def ask_claude(text, key, model):
    import requests
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": model, "max_tokens": 1024,
              "messages": [{"role": "user", "content": PROMPT.format(cats=", ".join(CATEGORIES), text=text)}]},
        timeout=60,
    )
    if r.status_code != 200:
        try:
            msg = r.json().get("error", {}).get("message", r.text[:200])
        except ValueError:
            msg = r.text[:200]
        raise RuntimeError(f"API error {r.status_code}: {msg}")
    body = r.json()
    out = "".join(b.get("text", "") for b in body.get("content", []) if b.get("type") == "text")
    match = re.search(r"\{.*\}", out, re.S)
    data = json.loads(match.group(0)) if match else {}
    usage = body.get("usage", {})
    return data, usage.get("input_tokens", 0) + usage.get("output_tokens", 0)


def route(category, score, confidence):
    """Decide the queue. Severe harms and uncertain calls always go to a person."""
    if category in ALWAYS_URGENT:
        return "P0 urgent human review and escalation"
    if score >= 15:
        return "P1 human review within 1 hour"
    if score >= 8 or confidence != "high":
        return "P2 human review within 24 hours"
    return "P3 close with 10% QA sampling"


def bar_svg(counts, width=520):
    items = sorted(counts.items(), key=lambda x: -x[1])
    top = max([v for _, v in items] or [1])
    rows = []
    for i, (label, value) in enumerate(items):
        y = i * 28
        w = int((width - 220) * value / top)
        rows.append(f'<text x="0" y="{y + 17}" font-size="13">{html.escape(label)}</text>'
                    f'<rect x="210" y="{y + 4}" width="{w}" height="18" rx="3" fill="#1F4E79"></rect>'
                    f'<text x="{215 + w}" y="{y + 17}" font-size="13">{value}</text>')
    return f'<svg width="{width}" height="{len(items) * 28 + 4}" role="img">{"".join(rows)}</svg>'


def write_dashboard(rows, kpis, path):
    cards = "".join(f'<div class="card"><div class="num">{html.escape(str(v))}</div><div>{html.escape(k)}</div></div>'
                    for k, v in kpis.items())
    table = "".join(
        f"<tr><td>{r['report_id']}</td><td>{r['category']}</td><td>{r['risk_score']}</td>"
        f"<td>{html.escape(r['queue'])}</td><td>{'yes' if r['matches_human_label'] == 'yes' else 'no'}</td></tr>"
        for r in sorted(rows, key=lambda r: -int(r["risk_score"])))
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>Trust triage dashboard</title>
<style>body{{font-family:Arial,sans-serif;margin:24px;color:#222}}.cards{{display:flex;flex-wrap:wrap;gap:12px}}
.card{{border:1px solid #ddd;border-radius:8px;padding:12px 16px;min-width:150px}}.num{{font-size:26px;font-weight:bold;color:#1F4E79}}
table{{border-collapse:collapse;margin-top:12px}}td,th{{border:1px solid #ddd;padding:6px 10px;font-size:13px;text-align:left}}</style></head>
<body><h1>Trust triage dashboard</h1><p>Synthetic reports only. Risk score is impact times likelihood, from 1 to 25.</p>
<div class="cards">{cards}</div>
<h2>Reports by harm type</h2>{bar_svg(Counter(r['category'] for r in rows))}
<h2>Reports by queue</h2>{bar_svg(Counter(r['queue'] for r in rows))}
<h2>All reports, highest risk first</h2><table><tr><th>ID</th><th>Category</th><th>Risk</th><th>Queue</th><th>Matches human label</th></tr>{table}</table>
</body></html>"""
    Path(path).write_text(page)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("--mock", action="store_true", help="offline, keyword baseline only")
    ap.add_argument("--out", default="output")
    args = ap.parse_args()

    load_env()
    key, model = os.environ.get("ANTHROPIC_API_KEY"), os.environ.get("ANTHROPIC_MODEL", "claude-haiku-5-5")
    if not args.mock and (not key or key == "your-key-here"):
        raise SystemExit("No API key found. Add it to .env (see .env.example) or run with --mock.")

    with open(args.input, newline="") as f:
        reports = list(csv.DictReader(f))

    rows, tokens, failures, start = [], 0, [], time.time()
    baseline_hits = 0
    for rep in reports:
        base, _ = keyword_baseline(rep["report_text"])
        baseline_hits += base["category"] == rep.get("human_label")
        if args.mock:
            data, used = base, 0
        else:
            try:
                data, used = ask_claude(rep["report_text"], key, model)
            except Exception as e:  # fall back to the baseline and record the failure
                data, used = base, 0
                failures.append(str(e))
        tokens += used
        cat = data.get("category") if data.get("category") in IMPACT else "not_violating"
        try:
            likelihood = max(1, min(5, int(data.get("likelihood", 3))))
        except (TypeError, ValueError):
            likelihood = 3
        conf = data.get("confidence", "low")
        score = IMPACT[cat] * likelihood
        rows.append({
            "report_id": rep["report_id"], "submitted_at": rep["submitted_at"], "category": cat,
            "impact": IMPACT[cat], "likelihood": likelihood, "risk_score": score, "confidence": conf,
            "queue": route(cat, score, conf), "reason": data.get("reason", ""),
            "human_label": rep.get("human_label", ""),
            "matches_human_label": "yes" if cat == rep.get("human_label") else "no",
        })

    out = Path(args.out)
    out.mkdir(exist_ok=True)
    with open(out / "triaged.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    n = len(rows)
    to_human = sum(not r["queue"].startswith("P3") for r in rows)
    agree = sum(r["matches_human_label"] == "yes" for r in rows)
    kpis = {
        "Reports triaged": n,
        "Sent to human review": f"{to_human} ({100 * to_human // n}%)",
        "P0 and P1 urgent": sum(r["queue"][:2] in ("P0", "P1") for r in rows),
        "Agreement with human labels": f"{100 * agree // n}%",
        "Keyword baseline agreement": f"{100 * baseline_hits // n}%",
        "Low confidence calls": sum(r["confidence"] == "low" for r in rows),
        "Tokens used": f"{tokens:,}",
    }
    write_dashboard(rows, kpis, out / "dashboard.html")

    if failures:
        print(f"WARNING: {len(failures)} of {n} API calls failed and used the baseline. First error: {failures[0]}")
    for k, v in kpis.items():
        print(f"{k}: {v}")
    print(f"Finished in {time.time() - start:.0f}s. Saved {out / 'triaged.csv'} and {out / 'dashboard.html'}")


if __name__ == "__main__":
    main()
