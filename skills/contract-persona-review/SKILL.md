---
name: contract-persona-review
description: Review a built UI before launch as an evidence-grounded user persona to find where tasks would break behaviour contracts or restore old workarounds.
---

# Contract persona review

## Steps

1. Read the Feature Requirements documents and their Behaviour contract sections. Use [contract.schema.json](references/contract.schema.json), [examples.md](references/examples.md) and [anti-patterns.md](references/anti-patterns.md) to interpret promises, populations, metrics and tolerances. If only contracts are provided, use their requirement statements and evidence and state that limitation.
2. For the billing demo, read [persona-billing-clerk.md](references/persona-billing-clerk.md). Preserve who actually said each quote; another clerk's contract evidence is not this persona's own statement. For other clients, ground a persona in their supplied evidence before reviewing.
3. For each requested contract, walk an eligible task as that persona through the supplied UI code: entry, field discovery, navigation, validation, submit, return paths and workarounds. Follow the HTML and JavaScript together. If a browser is available, use it for permitted interactions and distinguish observations from code-based inferences; do not submit live data without authorization.
4. Compare the path with the actual promise and expected observable events. Use the project's event catalog, or the synthetic [event-catalog.json](references/event-catalog.json), to distinguish missing instrumentation from demonstrated user behaviour. Report every supported obstacle that breaks a contract or pushes the user toward her old workaround. A static review can identify risk; it cannot establish a measured weekly breach.
5. Return the table below with source locations and the supporting quote's attribution. State contracts with no supported finding and review limits. Keep contract risks separate from preferences.

## Rules

- No finding without a contract ID and a supporting, attributed quote. Do not invent user needs, daily volume, emotions or observed behaviour.
- Separate **breaks a contract / contract risk** from **preference**. A secondary concern is not a contract failure merely because it is inconvenient.
- Explain severity from the promise, affected task and evidence, not an imagined measured failure rate. Mark uncertain paths as needing confirmation.
- Never change code, contract targets, monitoring settings or evidence while reviewing.

## Output format

State reviewed files, contracts and method (code walkthrough and any browser observations). Under **Contract findings**, return:

| Contract ID | What she'd hit | Her supporting quote | Severity | Suggested fix |
|---|---|---|---|---|

Put file/line references and the causal path in “What she'd hit”; include speaker and interview/timestamp with each quote, identifying evidence from another clerk explicitly. Follow with **Preferences** (clearly labelled, only when supported) and **Coverage and limits**, including contracts with no finding. Do not report a contract risk as measured post-launch drift.
