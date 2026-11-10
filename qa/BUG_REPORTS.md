# Bug Reports: Trust Triage

Found while testing against [TEST_PLAN.md](TEST_PLAN.md). Every bug reproduces with `python qa/qa_checks.py`.

| ID | Severity | Summary | Status |
|---|---|---|---|
| BUG-01 | High | Off-list category from the model is treated as harmless and can be auto-closed | Open |
| BUG-02 | Medium | Keyword fallback sends harmless reports to urgent queues | Open |
| BUG-03 | Medium | Output does not show which rows used the fallback | Open |
| BUG-04 | Low | Empty file or missing report text crashes the run | Open |
| BUG-05 | Low | Unlabelled rows count as disagreements in the agreement KPI | Open |
| BUG-06 | Low | Report ID is not escaped in the dashboard | Open |

---

## BUG-01. Off-list category from the model is treated as harmless and can be auto-closed

**Severity.** High. A harmful report can be closed without a person seeing it.

**Steps to reproduce**
1. Simulate a model response of `{"category": "fraud", "likelihood": 5, "confidence": "high"}` (TC03).
2. Run it through the same handling as `main()`.

**Expected.** Any category the tool does not recognise goes to human review.
**Actual.** `fraud` is not an exact match for `fraud_scam`, so it becomes `not_violating`, scores 5 and is routed to **P3, close with 10% QA sampling**. The same happens for `Fraud_Scam` with a capital letter.

**Impact.** Models sometimes shorten or reformat labels. Each time that happens on a high-confidence call, a scam report can be closed with only a 1 in 10 chance of review.
**Cause.** Line 179 maps any unknown category to `not_violating`.
**Suggested fix.** Treat an unknown category as low confidence, or map it to its own `needs_review` value, so it can never reach P3. Normalise case first.

---

## BUG-02. Keyword fallback sends harmless reports to urgent queues

**Severity.** Medium. Urgent reviewers lose time on false alarms when the API is down.

**Steps to reproduce**
1. Pass "The audio had a minor glitch on playback" to `keyword_baseline` (TC04).
2. Also try "My bank holiday playlist voice is too quiet" and "This is a hate-free podcast".

**Expected.** None of these reach P0 or P1.
**Actual.** "minor" matches child safety and goes to **P0**. "bank" matches fraud and goes to **P1**. "hate-free" matches harassment and goes to **P2**.

**Impact.** The baseline is also the live fallback when the API fails, so during an outage these false alarms reach real queues.
**Cause.** Keywords match anywhere inside the text, with no word boundaries or context.
**Suggested fix.** Match whole words, drop ambiguous words like "minor" and "bank" or require a second signal, and send fallback calls to P2 unless the match is strong.

---

## BUG-03. Output does not show which rows used the fallback

**Severity.** Medium. Decisions cannot be audited.

**Steps to reproduce**
1. Make every API call fail (TC05).
2. Open `output/triaged.csv`.

**Expected.** A column showing whether each decision came from Claude or the keyword fallback.
**Actual.** No such column. The console prints one warning line, but the CSV and dashboard look the same as a normal run. The KPI "Agreement with human labels" then reports the fallback's accuracy as if it were the model's.

**Impact.** A reviewer cannot tell which decisions to trust less, and the headline accuracy number can be misleading after an outage.
**Suggested fix.** Add a `decision_source` column and show the number of fallback rows as a KPI card.

---

## BUG-04. Empty file or missing report text crashes the run

**Severity.** Low. The run fails with no useful message.

**Steps to reproduce**
1. Run on a CSV with only a header row (TC06).
2. Run on a CSV with a row that has no `report_text` (TC07).

**Expected.** A clear message, and bad rows skipped or flagged.
**Actual.** `IndexError: list index out of range` for the empty file, and `AttributeError: 'NoneType' object has no attribute 'lower'` for the missing text.

**Suggested fix.** Check for zero rows before writing output, and skip or flag rows with empty text.

---

## BUG-05. Unlabelled rows count as disagreements in the agreement KPI

**Severity.** Low. The accuracy KPI is understated.

**Steps to reproduce.** Run one labelled and one unlabelled row that are both classified correctly (TC08).
**Expected.** 100%, because the only labelled row is correct.
**Actual.** 50%. The unlabelled row is counted as a miss.
**Suggested fix.** Measure agreement only over rows that have a human label, and show how many were labelled.

---

## BUG-06. Report ID is not escaped in the dashboard

**Severity.** Low. Untrusted text is written into the page as HTML.

**Steps to reproduce.** Use the report ID `<b>R1</b>` (TC09).
**Expected.** The ID shows as plain text.
**Actual.** The tag is written into the page as HTML, because `report_id` and `category` are not passed through `html.escape` in the table.
**Suggested fix.** Escape every value written into the table.
