"""QA checks for triage.py. Run from the repo root: python qa/qa_checks.py

Runs offline. No API key needed. Each check prints EXPECTED and ACTUAL.
A FAIL here matches a bug in qa/BUG_REPORTS.md.
"""
import csv, importlib.util, os, pathlib, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("triage", ROOT / "triage.py")
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
results = []

def check(tc, bug, expected, actual, ok):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {tc}{'  (' + bug + ')' if bug and not ok else ''}\n      expected: {expected}\n      actual:   {actual}")

def run(rows, header=("report_id", "submitted_at", "report_text", "human_label")):
    d = pathlib.Path(tempfile.mkdtemp()); f = d / "in.csv"
    with open(f, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(header); w.writerows(rows)
    p = subprocess.run([sys.executable, str(ROOT / "triage.py"), str(f), "--mock", "--out", str(d / "o")],
                       cwd=d, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip().splitlines()[-1], d / "o"

def score(cat, lk, conf):
    cat = cat if cat in t.IMPACT else "not_violating"
    return t.route(cat, t.IMPACT[cat] * lk, conf)

# TC01 regression: the sample file still runs end to end
code, last, out = run(list(csv.reader(open(ROOT / "reports.csv")))[1:])
check("TC01 sample file runs in mock mode", "", "exit 0, 20 rows", f"exit {code}, {sum(1 for _ in open(out / 'triaged.csv')) - 1} rows", code == 0)

# TC02 routing boundaries
cases = [("child_safety", 1, "high", "P0"), ("fraud_scam", 15, "high", "P1"), ("fraud_scam", 14, "high", "P2"),
         ("spam_other", 8, "high", "P2"), ("spam_other", 7, "high", "P3"), ("spam_other", 7, "medium", "P2")]
got = [t.route(c, s, k)[:2] for c, s, k, _ in cases]
check("TC02 routing thresholds P0 to P3", "", [e for *_, e in cases], got, got == [e for *_, e in cases])

# TC03 model returns a category name that is not exactly on the list
q = score("fraud", 5, "high")
check("TC03 off-list category from the model", "BUG-01", "sent to human review", q, not q.startswith("P3"))

# TC04 keyword fallback on harmless wording
q = t.route("child_safety", 5 * 3, "low") if t.keyword_baseline("The audio had a minor glitch on playback")[0]["category"] == "child_safety" else "not P0"
check("TC04 harmless report mentioning a 'minor glitch'", "BUG-02", "not P0", q, not q.startswith("P0"))

# TC05 fallback rows visible in the output
cols = open(out / "triaged.csv").readline().strip().split(",")
check("TC05 output shows which rows used the keyword fallback", "BUG-03", "a source or fallback column", cols, any("source" in c or "fallback" in c for c in cols))

# TC06 empty input file
code, last, _ = run([])
check("TC06 header-only CSV", "BUG-04", "clear message, no traceback", last, "Error" not in last)

# TC07 row with no report text
code, last, _ = run([["R900", "2026-11-01"]])
check("TC07 row missing report_text", "BUG-04", "row skipped or flagged, no traceback", last, "Error" not in last)

# TC08 unlabelled rows in the agreement KPI
code, last, out = run([["R1", "2026-11-01", "scam call asking for bank details", "fraud_scam"],
                       ["R2", "2026-11-01", "scam call asking for bank details", ""]])
html = open(out / "dashboard.html").read()
check("TC08 agreement ignores unlabelled rows", "BUG-05", "100% (1 of 1 labelled)", "50%" if ">50%<" in html else "100%", ">100%<" in html)

# TC09 HTML in report_id
code, last, out = run([["<b>R1</b>", "2026-11-01", "spam message", "spam_other"]])
check("TC09 report_id is escaped in the dashboard", "BUG-06", "&lt;b&gt;R1&lt;/b&gt;", "raw <b> tag" if "<td><b>R1</b></td>" in open(out / "dashboard.html").read() else "escaped", "<td><b>R1</b></td>" not in open(out / "dashboard.html").read())

print(f"\n{sum(results)} passed, {len(results) - sum(results)} failed")
