# Synthetic behaviour contract examples

Source: `contracts/medicare_contracts.json`, C-01 through C-05. All numbers and quotes are planted demo values; do not reuse them as facts about another client.

# C-01 / R-01: Every claim that needs prior authorization records the authorization number in its own field.

Feature: Claim submission · Persona: billing_clerk · Source: Pact behaviour contract C-01

## Requirement

Every claim that needs prior authorization records the authorization number in its own field.

## Evidence

- "If it needs prior auth I put the number in the notes, or sometimes just 'see fax'." (Billing clerk 2, INT-01 14:32, answer to AI question Q-12)
- "Pretty much every imaging claim for Medicare Advantage needs one." (Billing clerk 2, INT-01 14:51, answer to AI question Q-14)

## Confidence

high; said: yes / did: yes / code: yes. Said, done and coded all agree. The workaround exists because the code required it.

## Behaviour contract

Promise: Every claim that needs prior authorization records the authorization number in its own field.

Role: `billing_clerk`. Population: Submitted claims whose procedure requires prior authorization. Filter: `{"requires_prior_auth": true}`. Signal: `field_usage`.

| Metric ID | Description | Comparator | Target | Tolerance | Unit |
|---|---|---|---|---|---|
| pa_field_fill_rate | Share of prior-auth claims with the prior-auth field filled | >= | 0.95 | 0.05 | share |
| pa_in_notes_rate | Share of prior-auth claims with an auth number typed into notes (the legacy workaround) | <= | 0.05 | 0.05 | share |

Query definitions:

- `pa_field_fill_rate`: `field_fill_rate`, params `{"event": "claim_submitted", "flag": "prior_auth_number_filled"}`.
- `pa_in_notes_rate`: `detector_rate`, params `{"event": "claim_submitted", "tag": "auth_number"}`.

Baseline source: `legacy_logs`. Values: `{"pa_in_notes_rate": 0.71}`.

Baseline note: The legacy system had no prior-auth field. Rule PA-SCAN accepted a claim only if the notes contained 'AUTH'. Most clerks typed the number into notes; the rest wrote 'see fax'.

Events to instrument: `claim_submitted`, `claim_tab_viewed`, `ui_click`.

Window: weekly; min_tasks = 30; min_people = 5; learning_period_weeks = 2; consecutive_breaches_for_drift = 2.

Monitored version of this requirement's entry in Product Overview › Success Metrics.

---

# C-02 / R-02: A billing clerk can submit a routine clean claim in about five minutes or less.

Feature: Claim submission · Persona: billing_clerk · Source: Pact behaviour contract C-02

## Requirement

A billing clerk can submit a routine clean claim in about five minutes or less.

## Evidence

- "A normal claim takes me maybe four minutes if nothing's weird." (Billing clerk 1, INT-02 06:10)

## Confidence

medium; said: yes / did: yes / code: no. Time is behaviour, not a coded rule.

## Behaviour contract

Promise: A billing clerk can submit a routine clean claim in about five minutes or less.

Role: `billing_clerk`. Population: Claims submitted clean on the first pass. Filter: `{"first_pass_clean": true}`. Signal: `time`.

| Metric ID | Description | Comparator | Target | Tolerance | Unit |
|---|---|---|---|---|---|
| median_submit_seconds | Median time from opening a claim to submitting it | <= | 300 | 75 | seconds |

Query definitions:

- `median_submit_seconds`: `median_duration`, params `{"end_event": "claim_submitted", "start_event": "claim_opened"}`.

Baseline source: `both`. Values: `{"median_submit_seconds": 260}`.

Baseline note: Clerks estimated about four minutes; legacy logs show a 260 s median.

Events to instrument: `claim_opened`, `claim_submitted`.

Window: weekly; min_tasks = 30; min_people = 5; learning_period_weeks = 2; consecutive_breaches_for_drift = 2.

Monitored version of this requirement's entry in Product Overview › Success Metrics.

---

# C-03 / R-03: Clerks finish a claim in one sitting without repeatedly reopening it.

Feature: Claim submission · Persona: billing_clerk · Source: Pact behaviour contract C-03

## Requirement

Clerks finish a claim in one sitting without repeatedly reopening it.

## Evidence

- "If I have to open a claim twice, something went wrong." (Billing clerk 1, INT-02 09:44, answer to AI question Q-05)

## Confidence

medium; said: yes / did: yes / code: no. Behavioural expectation backed by logs.

## Behaviour contract

Promise: Clerks finish a claim in one sitting without repeatedly reopening it.

Role: `billing_clerk`. Population: All submitted claims. Filter: `{}`. Signal: `path`.

| Metric ID | Description | Comparator | Target | Tolerance | Unit |
|---|---|---|---|---|---|
| multi_reopen_rate | Share of claims reopened more than once before submission | <= | 0.1 | 0.05 | share |

Query definitions:

- `multi_reopen_rate`: `path_conformance`, params `{"loop_event": "claim_reopened", "max_loops": 1, "task_end": "claim_submitted", "task_start": "claim_opened"}`.

Baseline source: `legacy_logs`. Values: `{"multi_reopen_rate": 0.06}`.

Baseline note: Legacy users rarely reopened a claim more than once.

Events to instrument: `claim_opened`, `claim_reopened`, `claim_submitted`.

Window: weekly; min_tasks = 30; min_people = 5; learning_period_weeks = 2; consecutive_breaches_for_drift = 2.

Monitored version of this requirement's entry in Product Overview › Success Metrics.

---

# C-04 / R-04: When a patient's coverage changes after the date of service, eligibility is re-checked before the claim goes out.

Feature: Eligibility changes · Persona: billing_clerk · Source: Pact behaviour contract C-04

## Requirement

When a patient's coverage changes after the date of service, eligibility is re-checked before the claim goes out.

## Evidence

- "Oh, that. If coverage changes after the visit, it lands in my queue and I re-run eligibility." (Billing clerk 2, INT-01 21:05, answer to AI question Q-19)

## Confidence

high; said: yes / did: yes / code: yes. Nobody mentioned this until an AI code-gap question asked about it.

## Behaviour contract

Promise: When a patient's coverage changes after the date of service, eligibility is re-checked before the claim goes out.

Role: `billing_clerk`. Population: Coverage changes that land after a visit has been billed or is about to be. Filter: `{"after_date_of_service": true}`. Signal: `sequence`.

| Metric ID | Description | Comparator | Target | Tolerance | Unit |
|---|---|---|---|---|---|
| recheck_within_48h_rate | Share of post-visit coverage changes followed by an eligibility check within 48 hours | >= | 0.9 | 0.1 | share |

Query definitions:

- `recheck_within_48h_rate`: `followup_within`, params `{"followup_event": "eligibility_checked", "trigger_event": "coverage_changed", "within_hours": 48}`.

Baseline source: `legacy_logs`. Values: `{"recheck_within_48h_rate": 0.83}`.

Baseline note: Legacy rule RETRO-ELIG pushed these claims into a clerk's queue.

Events to instrument: `coverage_changed`, `eligibility_checked`.

Window: weekly; min_tasks = 30; min_people = 5; learning_period_weeks = 2; consecutive_breaches_for_drift = 2.

Monitored version of this requirement's entry in Product Overview › Success Metrics.

---

# C-05 / R-05: Denials are tracked inside the system, so no side spreadsheet is needed.

Feature: Denial management · Persona: denial_specialist · Source: Pact behaviour contract C-05

## Requirement

Denials are tracked inside the system, so no side spreadsheet is needed.

## Evidence

- "We keep a spreadsheet of every denial because the system loses track of them after a month." (Denial specialist 1, INT-03 03:27)

## Confidence

medium; said: yes / did: yes / code: no. A workaround; the new denial tracker should replace it.

## Behaviour contract

Promise: Denials are tracked inside the system, so no side spreadsheet is needed.

Role: `denial_specialist`. Population: Denial specialists' working weeks. Filter: `{}`. Signal: `absence`.

| Metric ID | Description | Comparator | Target | Tolerance | Unit |
|---|---|---|---|---|---|
| denial_export_rate | Exports of the denials list to CSV per person per week | <= | 1.0 | 1.0 | per_person_week |

Query definitions:

- `denial_export_rate`: `rate_per_person_week`, params `{"event": "export_csv", "where": {"source_view": "denials"}}`.

Baseline source: `legacy_logs`. Values: `{"denial_export_rate": 6.2}`.

Baseline note: Legacy users exported the denials list about six times a week into a shared spreadsheet.

Events to instrument: `export_csv`.

Window: weekly; min_tasks = 5; min_people = 5; learning_period_weeks = 2; consecutive_breaches_for_drift = 2.

Monitored version of this requirement's entry in Product Overview › Success Metrics.

---
