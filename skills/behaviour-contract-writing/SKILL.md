---
name: behaviour-contract-writing
description: Use when writing or reviewing a Feature Requirement that came from interviewing legacy-system users, to attach a measurable behaviour contract (expectations, tolerance, baseline, events, window) that usage data can check after launch. Extends Software Factory's Requirements Writing Rules.
---

# Behaviour contract writing

A behaviour contract is the measurable version of one requirement: what users must be able to do in the new system, stated as numbers that usage events can confirm or break. Software Factory's Requirements Writing Rules still apply to the requirement text. This skill adds the contract underneath it.

The contract format is `references/contract.schema.json`. Worked examples are in `references/examples.md`. Read `references/anti-patterns.md` before you finish.

## Steps

1. **Start from evidence.** Collect the interview quotes behind the requirement, each with speaker, interview ID, timestamp and the question ID that prompted it (null if unprompted). No quote, no contract.
2. **Write the requirement** as one sentence about an outcome the user needs, not about a screen. Example: "Every claim that needs prior authorization records the authorization number in its own field."
3. **Pick the signal shape** that would show the promise being kept:
   - `field_usage`: a field is filled when it should be (fill rate).
   - `time`: a task finishes within a time (median seconds).
   - `path`: a task finishes without rework (reopen rate).
   - `sequence`: event B follows event A within a time (re-check within 48 h).
   - `absence`: a workaround stops happening (exports per person per week).
4. **Write each expectation** with `metric_id`, a plain `description`, `comparator`, `target`, `unit` and `tolerance`. Add a second expectation for the legacy workaround when one exists (for example `pa_in_notes_rate <= 0.05`), so you can see whether people fall back to it.
5. **Set the baseline from legacy logs**, not from what people said. Put the quote's number in the evidence, and the log value in `baseline.values`, with a `baseline.note` that explains the difference. If they disagree, that is a say-vs-do gap: set `confidence.said` / `did` / `code` accordingly.
6. **List `events_required`.** These are the typed events (with flags and tags, never free text) the new build must emit so the contract can be checked. This list is an instrumentation requirement for the build.
7. **Set the window:** weekly, `min_tasks`, `min_people` (privacy floor, at least 5), `learning_period_weeks` (usually 2) and `consecutive_breaches_for_drift` (usually 2).
8. **Link code.** Add `code_refs` to the legacy rule that created the behaviour (for example `legacy/CLMEDIT.cbl`, rule `PA-SCAN`), if one exists.
9. **Set confidence** (`high`, `medium`, `low`) from whether it was said, done (logs) and coded, with a one-line note.
10. **If usage can't show it** (trust, phone calls, sticky notes), write an open loop instead: the requirement, `why_unmeasurable`, and a suggested human check or event to instrument.

## Rules

- One contract per requirement. One requirement per contract.
- Every expectation has a tolerance. Breach is beyond the tolerance; broken is beyond twice the tolerance.
- Targets never come from a number guessed in the interview alone.
- No event may carry free text, names or PHI.
- A contract observes. It never blocks a user or changes the system.

## Output format

Add this section to the Feature Requirements document, after the requirement and evidence:

```markdown
## Behaviour contract

Promise: <requirement statement>

| metric_id | description | comparator | target | tolerance | unit |
|---|---|---|---|---|---|
| ... | ... | ... | ... | ... | ... |

Baseline (<source>): <metric = value, ...>.
Baseline note: <why the baseline is what it is>

Events to instrument: `<event>`, ...
Window: weekly, at least <min_tasks> tasks and <min_people> people per window, <n> learning weeks, drift after <n> consecutive breaches.

Monitored version of this requirement's entry in Product Overview › Success Metrics.
```

Also produce the contract as JSON that validates against `references/contract.schema.json`.
