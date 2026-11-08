# Behaviour contracts

A behaviour contract says what the usage data should look like if one requirement is being met. It is the shared agreement every workstream builds against:

- **Backend (interview engine)** produces contracts in this format and fills their `evidence` from interview answers.
- **Data** generates legacy logs and post-launch events that match `event_catalog`, and plants drift in C-01.
- **Web (evidence board)** displays contracts, their evidence lineage (`question_id`, `question_origin`), status and cost.
- **Drift detector** computes each `expectation` with the query named in `template`.

## Files

| File | What it is |
|---|---|
| `contract.schema.json` | JSON Schema for one contract. Validate against it. |
| `medicare_contracts.json` | Event catalog, five example contracts (one per signal shape) and one open loop. |

## The five contracts

| ID | Requirement | Shape | Demo role |
|---|---|---|---|
| C-01 | Prior-auth number goes in its own field | field_usage | **The one that drifts end to end.** Clerks fall back to typing it in notes because the field is on a second tab. |
| C-02 | Routine claim in about five minutes | time | Should stay holding. |
| C-03 | Claims finished in one sitting | path | Should stay holding. |
| C-04 | Eligibility re-checked after post-visit coverage change | sequence | Showcases an AI code-gap question (Q-19) that produced a contract. |
| C-05 | Denials tracked in-system, no side spreadsheet | absence | Could be a second drift or a decoy. |

`open_loops` holds requirements with no measurable footprint (R-06). They are reported as needing human QA, not checked.

## Rules everyone must keep

- **Per role, never per person.** `actor_hash` exists only to enforce `min_people` (5). It is never shown.
- **No free text or patient data in events.** Notes are pattern-matched inside the app; only tags such as `auth_number` leave it. The prior-auth number itself is never sent, only `prior_auth_number_filled`.
- **Drift rules:** weekly windows, skip the first `learning_period_weeks`, a breach needs `consecutive_breaches_for_drift` weeks in a row, and "broken" means twice the tolerance.
- **All numbers, quotes and question IDs here are planted demo values** (`demo_value: true`). Say so on stage.

## Rule IDs referenced

`PA-SCAN` and `RETRO-ELIG` in `legacy/CLMEDIT.cbl`. The rest of the planted COBOL rules (timely filing, modifier, payer exception, duplicate check, dead path) should be added to the answer key using the same ID style.
