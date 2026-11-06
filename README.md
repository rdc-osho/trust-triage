# Trust Triage for Voice AI Abuse Reports

Voice AI makes it easy to clone a voice, which also makes it easy to misuse. Trust teams receive reports about impersonation, scam calls, election misinformation, cloned voices used without consent and more. This tool shows how those reports can be triaged quickly while making sure the most harmful cases always reach a person first.

All 20 reports in `reports.csv` are synthetic examples I wrote for this demo. No real people are named.

## What it does

1. Reads abuse reports from a CSV file.
2. Classifies each report into one of eight harm types using the Claude API.
3. Scores risk as **impact times likelihood**, each from 1 to 5, giving a score from 1 to 25. Impact is fixed per harm type, and likelihood comes from the evidence in the report.
4. Routes every report to a queue.
   * **P0** child safety, always urgent human review and escalation
   * **P1** risk score of 15 or more, human review within 1 hour
   * **P2** risk score of 8 or more, or any call the model is not sure about, human review within 24 hours
   * **P3** low risk and high confidence, closed with 10% sampled for quality checks
5. Compares the AI result with a simple keyword baseline and with human labels, so accuracy is measured rather than assumed.
6. Builds a dashboard of trust KPIs in `output/dashboard.html`.

## Results from the first real run

20 reports triaged in 36 seconds using 9,119 tokens, which cost a few pence.

| Measure | Result |
|---|---|
| Agreement with human labels | **85%** with Claude, against **55%** for the keyword baseline |
| Sent to human review | 16 of 20 (80%) |
| Urgent P0 and P1 cases | 12 |
| Low confidence calls | 1 |

The keyword baseline missed the election robocall, the cloned voice used without consent and the hate speech podcast, all serious harms. Claude caught all of them.

**The three disagreements taught me the most.** None of them were careless mistakes. Each report genuinely involved two harms at once.

* **R001.** A cloned celebrity voice promoting a crypto giveaway. I labelled it impersonation, Claude labelled it a scam. It is both.
* **R002.** A cloned voice of a family member asking for money. I labelled it a scam, Claude labelled it a voice cloned without consent. Again, both.
* **R007.** A cloned singer releasing a song she never recorded. I labelled it impersonation of a public figure, Claude labelled it a clone without consent.

**What I learned.** The weak point was my single label design, not the model. Real abuse often combines impersonation and fraud, so the next version should allow a primary and a secondary harm type and score risk on the more severe one. In every case the report still reached a human reviewer, which is why routing on severity matters more than getting the label perfect.

## Why it is built this way

* **People stay in control of serious harm.** Child safety never waits on a score, and anything uncertain goes to a human.
* **Accuracy is measured.** Every result is checked against a human label and a baseline, the same idea as calibration in content moderation.
* **No personal data leaves the report.** The prompt tells the model not to repeat personal details, and the API key stays in a local `.env` file that is never uploaded.

## How to run it

```
pip install -r requirements.txt
cp .env.example .env
python triage.py reports.csv
```

Add your own API key to `.env` first. To try it offline with the keyword baseline only, run `python triage.py reports.csv --mock`.

## Next steps

1. Allow a primary and a secondary harm type per report, scoring on the more severe one.
2. Track time to action from report to decision.
3. Add appeal outcomes and measure how often decisions are overturned.
4. Feed confirmed cases back into detection, such as voices that should be blocked from cloning.

## Tools

Python, Claude API, CSV and HTML.
