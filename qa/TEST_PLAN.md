# Test Plan: Trust Triage

**Scope.** `triage.py`, the AI workflow that classifies voice AI abuse reports, scores risk and routes each report to a review queue.
**Version tested.** `main` branch, November 2026.
**Tester.** Dami Osho

## Why this matters

The tool decides which reports a person sees first. The worst failure is a harmful report being closed without review. The second worst is a harmless report taking an urgent reviewer away from a real one. Testing focuses on those two risks first.

## Risk areas, in priority order

| # | Area | What could go wrong |
|---|---|---|
| 1 | Model output handling | The model returns something unexpected and a harmful report is closed |
| 2 | Fallback path | The API fails and the keyword fallback routes reports badly |
| 3 | Routing rules | A threshold is off by one and a report lands in the wrong queue |
| 4 | Input handling | A bad or empty CSV crashes the run |
| 5 | Reporting | KPIs or the dashboard show numbers that are wrong or unsafe |

## Test cases

All checks run offline with `python qa/qa_checks.py`. No API key is needed. Model responses are simulated, so every result can be reproduced.

| ID | Area | Test | Expected | Result |
|---|---|---|---|---|
| TC01 | Regression | Run the 20 sample reports in mock mode | Runs cleanly, 20 rows out | Pass |
| TC02 | Routing | Scores either side of every threshold (P0, 15, 14, 8, 7) and confidence high or medium | Each lands in the documented queue | Pass |
| TC03 | Model output | Model returns `fraud` instead of `fraud_scam`, high confidence | Sent to human review | **Fail, BUG-01** |
| TC04 | Fallback | Harmless report: "The audio had a minor glitch" | Not P0 | **Fail, BUG-02** |
| TC05 | Fallback | API fails for every call | Output shows which rows used the fallback | **Fail, BUG-03** |
| TC06 | Input | CSV with a header and no rows | Clear message, no crash | **Fail, BUG-04** |
| TC07 | Input | Row with no report text | Row skipped or flagged, no crash | **Fail, BUG-04** |
| TC08 | Reporting | One labelled and one unlabelled row, both correct | Agreement 100% of labelled rows | **Fail, BUG-05** |
| TC09 | Reporting | Report ID containing HTML | Shown as text in the dashboard | **Fail, BUG-06** |

## Summary

9 checks, 2 passed, 7 failed, 6 bugs logged in [BUG_REPORTS.md](BUG_REPORTS.md).
The routing rules work as documented. The weak points are what happens around them: unexpected model output, the fallback path and the input file.

## Regression checklist for future changes

Run after any change to the prompt, the categories, the routing rules or the model.

- [ ] `python qa/qa_checks.py` shows no new failures
- [ ] Mock run on `reports.csv` still produces 20 rows
- [ ] Every child safety report still lands in P0
- [ ] No report with an unrecognised category can reach P3
- [ ] Agreement with human labels is re-measured with the API and compared with the last run (85%)
- [ ] Dashboard opens and the KPI cards match `triaged.csv`

## Out of scope for this round

Live API accuracy beyond the measured 85%, speed under large files, and prompt injection inside report text. These are next.
