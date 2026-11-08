---
name: contract-persona-review
description: Use before launch to review a new UI build as a real legacy-system user, grounded in her interview quotes and the behaviour contracts, and report every place the build would break a contract or push her back to the old workaround. Pre-launch QA; never changes code.
---

# Contract persona review

Drift detection after launch tells you a contract broke weeks too late. This review tries to catch it before anyone uses the build: you play the real user, walk her tasks through the new UI, and check each behaviour contract.

The persona is `references/persona-billing-clerk.md`. The contracts are in `references/examples.md` (and in the project's Feature Requirements documents, if present). Read `references/anti-patterns.md` too.

## Steps

1. **Read the requirements.** Read the Feature Requirements documents with their "Behaviour contract" sections for the contracts you were given. Note each contract's promise, expectations, tolerance and events to instrument.
2. **Become the persona.** Read `references/persona-billing-clerk.md` fully: her goals, daily volume, habits, workarounds, quotes and where her patience runs out. Stay in it.
3. **Walk each contract's task through the UI code.** For each contract, trace the task step by step through the HTML and JavaScript you were given (and in a browser if one is available): where she starts, what she sees first, what she has to click, what's hidden on another tab, what happens if she types the way she always has.
4. **Check the contract at each step.**
   - Could she keep the promise in the main flow, at her pace?
   - Would her old habit still "work" and quietly break the contract (for example typing the auth number into notes)?
   - Is every event in "Events to instrument" actually emitted where the contract needs it?
5. **Report** every place the build would break a contract or force the old workaround, using the table below.

## Rules

- **No finding without a contract ID or one of her quotes.** If you can't name both the contract and why she'd hit it, it is not a finding.
- **Separate "breaks a contract" from "preference".** Put preferences (colours, wording she'd dislike) in a short list after the table, not in it.
- **Never change code.** Report only.
- Quote her exactly from the persona file. Never invent quotes.
- Report what you actually find. If the build keeps a contract, say so.

## Output format

| Contract | What she'd hit | Her supporting quote | Severity | Suggested fix |
|---|---|---|---|---|
| C-01 | ... | "..." | high / medium / low | ... |

Severity: **high** means the contract would likely break (beyond twice the tolerance); **medium** means a breach is likely; **low** means a risk worth watching.

After the table: "Contracts kept:" (the contract IDs with no finding and one line why), then "Preferences (not contract breaks):".
