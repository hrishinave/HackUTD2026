---
name: contract-interview
description: Extend a Requirements agent's interview mode to fill measurable behaviour-contract slots from user answers, legacy code and log facts.
---

# Contract interview

## Steps

1. Read the current requirement candidates, transcript, legacy rules, log facts and event catalog. Read [contract.schema.json](references/contract.schema.json), [examples.md](references/examples.md) and [anti-patterns.md](references/anti-patterns.md). The bundled [event-catalog.json](references/event-catalog.json) contains synthetic billing examples, not facts about a new client.
2. Track slots for each candidate: requirement and role, eligible tasks/population, rule and exceptions, quantity/frequency, current path and workaround, baseline, expected improvement/tolerance, events, window and quote lineage. Mark missing evidence explicitly.
3. Prefer questions about rules present in legacy code that the interviewee has not mentioned. Ask for concrete quantities and compare answers with legacy log facts. If sources disagree, ask a neutral follow-up and retain both accounts with attribution.
4. Ask one question at a time, at most 15 words. Wait for the answer. Follow the current answer before returning to lower-priority gaps. Examples: “What happens when coverage changes after the visit?”; “How many claims need that each day?”
5. Record each answer against the relevant contract slot using the exact quote, speaker, interview ID, timestamp and question ID/origin when available. Keep interview estimates separate from measured facts. Carry unresolved quantities, tolerances and instrumentation into follow-up decisions.
6. Summarize filled slots, contradictions and the next unanswered gap. Hand a measurable candidate to contract writing; route an unobservable need to an open loop with a suggested human check or event to instrument.

## Rules

- Never invent an answer, quantity, timestamp, quote or question ID. Use unknown for missing evidence; do not pass an incomplete candidate off as schema-valid.
- Do not disclose facilitator-only answers or turn a legacy rule into a leading answer. Ask the user how the task actually works.
- One spoken question, no more than 15 words; keep bookkeeping out of the spoken question.
- No raw patient data, notes or authorization numbers in telemetry. No automatic approval, monitoring enablement or external filing.
- Separate said/did/code confidence. A target is a proposed future promise, not a number the interviewee necessarily supplied.

## Output format

Return **Next question** (one question, at most 15 words) and a separate **Slot record** table:

| Candidate / contract | Slot | Answer / value | Exact quote and lineage | Source: said / did / code | Missing or conflicting evidence |
|---|---|---|---|---|---|

Then list **Unresolved contradictions**, **Decisions needed**, and **Open loops** with the event or human check each needs. Do not create a final contract without sufficient evidence and approval decisions.
