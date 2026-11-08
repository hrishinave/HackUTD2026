---
name: contract-interview
description: Use when interviewing a legacy-system user to gather requirements, so that each answer fills a behaviour contract slot with a quote and the questions target legacy rules nobody has mentioned yet. Extends the Software Factory Requirements agent's interview mode.
---

# Contract interview

An interview is where a behaviour contract gets its evidence. The goal is to fill each contract's slots (who, what promise, how often, how fast, what workaround) with the user's own words, and to surface rules that live only in the legacy code.

Contract format and examples: `references/contract.schema.json`, `references/examples.md`. Pitfalls: `references/anti-patterns.md`.

## Before the interview

1. List the contracts relevant to this person's role and the slots each still needs.
2. List the legacy code rules (for example the COBOL rule paragraphs) that apply to this role and have not come up in any interview yet. These are the most valuable questions: people rarely mention rules they no longer notice.
3. List the legacy log facts for this role (for example "71% of prior-auth claims have the auth number in notes", "median claim 260 s").

## During the interview

1. **One question at a time, at most 15 words.** It is spoken aloud; short questions get real answers.
2. **Prefer questions about unmentioned legacy rules.** Ask about the situation the rule handles, not the rule itself: "What happens when a patient's coverage changes after the visit?", not "Tell me about RETRO-ELIG."
3. **Ask for quantities.** "How long does that usually take?" "How many a week?" Then compare the answer with the legacy log fact. If they differ, ask one follow-up and record both; do not correct the person.
4. **Follow workarounds.** Phrases like "I just write…", "I always check it on a calculator", "I keep a spreadsheet" point to a requirement the system doesn't meet.
5. **Record every useful answer against a slot**, with the exact quote, timestamp and the question ID that prompted it.
6. **Note contradictions** between this person, other people, the manual and the code. Record them; never argue.

## Rules

- Never say patient names, claim numbers or any PHI aloud.
- Never invent a number for a contract from the interview alone. The quote is evidence; the target comes from the need and the logs.
- If an answer describes something usage events can't show (trust, phone calls), record it as an open loop with a suggested human check.
- Stop when every relevant contract slot has a quote, or the person's time is up.

## Output format (one line per answer)

```
<contract or open-loop ID> · <slot> · "<exact quote>" · <speaker>, <interview ID> <timestamp> · <question ID or unprompted> · log fact: <value or none> · say-vs-do: <match | differs | n/a>
```

Then a list of contradictions and open loops found, and the legacy rules still not covered.
