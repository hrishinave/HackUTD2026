# Example behaviour contracts (C-01 to C-05)

The five catalog contracts from the synthetic Medicare billing clinic, in the same layout as the
"Behaviour contract" section of a Pact Feature Requirements export. Synthetic data.

## C-01 (R-01, field_usage, billing_clerk)

Evidence:
- "If it needs prior auth I put the number in the notes, or sometimes just 'see fax'." (Billing clerk 2, INT-01 14:32)
- "Pretty much every imaging claim for Medicare Advantage needs one." (Billing clerk 2, INT-01 14:51)

Promise: Every claim that needs prior authorization records the authorization number in its own field.

| metric_id | description | comparator | target | tolerance | unit |
|---|---|---|---|---|---|
| pa_field_fill_rate | Share of prior-auth claims with the prior-auth field filled | >= | 0.95 | 0.05 | share |
| pa_in_notes_rate | Share of prior-auth claims with an auth number typed into notes (the legacy workaround) | <= | 0.05 | 0.05 | share |

Baseline (legacy_logs): pa_in_notes_rate = 0.71.
Baseline note: The legacy system had no prior-auth field. Rule PA-SCAN accepted a claim only if the notes contained 'AUTH'. Most clerks typed the number into notes; the rest wrote 'see fax'.

Events to instrument: `claim_submitted`, `claim_tab_viewed`, `ui_click`.
Window: weekly, at least 30 tasks and 5 people per window, 2 learning weeks, drift after 2 consecutive breaches.

Monitored version of this requirement's entry in Product Overview › Success Metrics.

## C-02 (R-02, time, billing_clerk)

Evidence:
- "A normal claim takes me maybe four minutes if nothing's weird." (Billing clerk 1, INT-02 06:10)

Promise: A billing clerk can submit a routine clean claim in about five minutes or less.

| metric_id | description | comparator | target | tolerance | unit |
|---|---|---|---|---|---|
| median_submit_seconds | Median time from opening a claim to submitting it | <= | 300 | 75 | seconds |

Baseline (both): median_submit_seconds = 260.
Baseline note: Clerks estimated about four minutes; legacy logs show a 260 s median.

Events to instrument: `claim_opened`, `claim_submitted`.
Window: weekly, at least 30 tasks and 5 people per window, 2 learning weeks, drift after 2 consecutive breaches.

Monitored version of this requirement's entry in Product Overview › Success Metrics.

## C-03 (R-03, path, billing_clerk)

Evidence:
- "If I have to open a claim twice, something went wrong." (Billing clerk 1, INT-02 09:44)

Promise: Clerks finish a claim in one sitting without repeatedly reopening it.

| metric_id | description | comparator | target | tolerance | unit |
|---|---|---|---|---|---|
| multi_reopen_rate | Share of claims reopened more than once before submission | <= | 0.1 | 0.05 | share |

Baseline (legacy_logs): multi_reopen_rate = 0.06.
Baseline note: Legacy users rarely reopened a claim more than once.

Events to instrument: `claim_opened`, `claim_reopened`, `claim_submitted`.
Window: weekly, at least 30 tasks and 5 people per window, 2 learning weeks, drift after 2 consecutive breaches.

Monitored version of this requirement's entry in Product Overview › Success Metrics.

## C-04 (R-04, sequence, billing_clerk)

Evidence:
- "Oh, that. If coverage changes after the visit, it lands in my queue and I re-run eligibility." (Billing clerk 2, INT-01 21:05)

Promise: When a patient's coverage changes after the date of service, eligibility is re-checked before the claim goes out.

| metric_id | description | comparator | target | tolerance | unit |
|---|---|---|---|---|---|
| recheck_within_48h_rate | Share of post-visit coverage changes followed by an eligibility check within 48 hours | >= | 0.9 | 0.1 | share |

Baseline (legacy_logs): recheck_within_48h_rate = 0.83.
Baseline note: Legacy rule RETRO-ELIG pushed these claims into a clerk's queue.

Events to instrument: `coverage_changed`, `eligibility_checked`.
Window: weekly, at least 30 tasks and 5 people per window, 2 learning weeks, drift after 2 consecutive breaches.

Monitored version of this requirement's entry in Product Overview › Success Metrics.

## C-05 (R-05, absence, denial_specialist)

Evidence:
- "We keep a spreadsheet of every denial because the system loses track of them after a month." (Denial specialist 1, INT-03 03:27)

Promise: Denials are tracked inside the system, so no side spreadsheet is needed.

| metric_id | description | comparator | target | tolerance | unit |
|---|---|---|---|---|---|
| denial_export_rate | Exports of the denials list to CSV per person per week | <= | 1.0 | 1.0 | per_person_week |

Baseline (legacy_logs): denial_export_rate = 6.2.
Baseline note: Legacy users exported the denials list about six times a week into a shared spreadsheet.

Events to instrument: `export_csv`.
Window: weekly, at least 5 tasks and 5 people per window, 2 learning weeks, drift after 2 consecutive breaches.

Monitored version of this requirement's entry in Product Overview › Success Metrics.

## Open loop R-06 (no contract)

Requirement: Clerks trust that claim totals are correct before submitting.
Why it can't be measured: Trust leaves no direct footprint in usage data, so no machine check is possible.
Suggested human check: Raise in 8090's post-launch user conversations.
