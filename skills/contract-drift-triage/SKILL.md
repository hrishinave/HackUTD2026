---
name: contract-drift-triage
description: Extend Triage Feedback for Pact contract-drift items by parsing their fixed header, linking the requirement and reusing a contract's Theme.
---

# Contract drift triage

Extend Software Factory's Triage Feedback workflow when the Feedback item's `content` starts with `Pact-Contract:`. The payload remains `{end_user_email, content}`; the service email is `usage-drift@pact.invalid`. The header lives inside `content`, not in new payload fields.

## Fixed Feedback header

This example is word for word the header produced by `server/feedback.py` (`HEADER_KEYS` and `_header`) for C-01 / F-01 with a cost of 15120, checked against merged P1 at `32d1c8c`:

```text
Pact-Contract: C-01
Requirement: R-01
Finding: F-01
Status: broken since week 4
Type: app_gap
Cost: $15,120/week at risk (demo value)
---
```

Keys and order are fixed; values vary per finding. `Requirement` comes from `lineage.requirement_id`, then the finding's `requirement_id`, then the matching contract's requirement ID, else `unknown`. `Status` is `<status> since week <first_breach_week>` (the producer defaults a missing status to `drifting`). `Type` is the finding's type, or `unknown`. `Cost` is `$<comma-formatted amount>/week at risk (demo value)` or exactly `unknown` when no cost exists. Do not round or rewrite the header while triaging. The existing prose follows the `---` line and ends with `Simulated data.`

## Steps

1. Recognise the prefix at the start of `content`, read `Key: value` lines until `---`, and preserve all six values. Read [contract.schema.json](references/contract.schema.json), [examples.md](references/examples.md) and [anti-patterns.md](references/anti-patterns.md) for the contract model. If a required header value is missing or unknown, flag the missing evidence rather than guessing it. Non-Pact items use the ordinary Triage Feedback workflow.
2. Resolve the Feature Requirement named by `Requirement:`. Read its statement and Behaviour contract, the finding's explanation and the attributed interview evidence. Use the project's event catalog (the bundled [event-catalog.json](references/event-catalog.json) is synthetic). Keep links to `Pact-Contract`, `Requirement` and `Finding`; if no quote is supplied, retrieve the linked contract's evidence or flag the item as needing evidence before presenting a supported finding.
3. Search existing Themes using `Pact-Contract` as the stable key before creating anything. Reuse the same Theme for every finding about that contract. Name it after the broken promise, using the requirement statement, and link it to the Feature Requirement; do not create a second Theme merely because a new Finding ID or week appears.
4. Use `Type:` to choose the response: `app_gap` → Work Order to remove the concrete workflow obstacle; `know_how_gap` → Work Order to improve discoverability or guidance; `stale_requirement` → requirement change for review with the client. If the type is unknown, keep the classification unresolved. Treat the finding's classification as evidence to assess, not proof of its cause.
5. Set priority from `Cost:` under the project's existing priority policy, considering the contract's criticality and confidence. Preserve the amount, weekly unit and `(demo value)` label. If no numeric priority policy exists, state relative cost-based urgency and the missing decision instead of inventing thresholds. `Cost: unknown` is not zero and requires a cost assessment.
6. Return the triage decision with its supporting quote and source links. In the Pact demo, filing is simulated with no live connection. If asked to file through the app, use `POST /api/findings/{finding_id}/file` (monitoring/client sending choices still apply); a repeat returns the original `feedback_number` with `already_filed: true`. Do not bypass file-once by posting directly to the stub. Creating or changing items in a connected Software Factory project requires the user's authorization.

## Rules

- Never create a second Theme for the same `Pact-Contract`. If Theme search is unavailable, return a proposed triage decision and flag deduplication as unverified.
- No supported finding without a contract ID and an attributed quote. Preserve the difference between the contract promise, measured drift and a causal hypothesis.
- Never infer an ID from display order, rewrite a requirement automatically, invent a cost or silently convert synthetic cost into real loss.
- Keep the payload shape and exact header unchanged. No live Software Factory connection exists in this demo; a local FB number proves only a simulated filing.

## Output format

Return the parsed six-field header verbatim, then:

| Contract / Finding | Feature Requirement | Theme: broken promise | Existing Theme / deduplication | Type and proposed action | Cost-based priority and basis | Supporting quote and source |
|---|---|---|---|---|---|---|

Finish with **Missing evidence / decisions** and **Filing status** (proposed, simulated FB number, or authorized external result). Report an existing Theme or FB number only when actually verified; preserve `already_filed` for repeated demo filings.
