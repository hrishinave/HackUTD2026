---
name: behaviour-contract-writing
description: Extend Feature Requirements with evidence-backed behaviour contracts when writing or revising measurable user requirements.
---

# Behaviour contract writing

Extend Software Factory's Requirements Writing Rules: keep the Feature Requirement and add a monitored promise to its Success Metrics. Use the client's evidence, not the demo's numbers.

## Steps

1. Read the Feature Requirement, interview quotes, relevant legacy rules and log facts. Read [contract.schema.json](references/contract.schema.json), [examples.md](references/examples.md) and [anti-patterns.md](references/anti-patterns.md). Check event names and properties against the project's event catalog; the supplied [event-catalog.json](references/event-catalog.json) is the synthetic billing example only.
2. Identify one promise, its requirement ID, role, eligible task population and observable footprint. Preserve the quote's speaker, interview ID, timestamp and question lineage. Separate what users said, logs show and code enforces.
3. Choose a supported signal and query template. Define metric ID, template parameters, comparator, target, unit and tolerance. Derive baselines from cited observations; distinguish observed baseline from proposed target. Record disagreements as hypotheses with sources rather than picking a winner.
4. Set weekly window rules: minimum tasks, at least five people, learning period and consecutive breaches. Specify the existing events required and any missing instrumentation. Record criticality and the basis of any cost estimate, labelling demo values.
5. Produce the Feature Requirement's Behaviour contract section using the examples' layout, plus a contract object matching the schema when the evidence supports all required fields. List missing decisions explicitly. A requirement with no measurable footprint becomes an open loop with evidence and a suggested human check or event to instrument.

## Rules

- Never invent interview quantities, quotes, baselines or IDs. A proposed target is a proposal until approved; schema completeness is not a reason to fabricate evidence.
- Include tolerance and the population denominator; do not treat a single unusual week as sustained drift.
- Use catalogued events with flags/IDs; never collect raw notes, patient data or authorization numbers. Compare groups by role, never report individuals or groups below the privacy floor.
- Keep confidence's said/did/code flags independent. An interview assertion alone does not establish observed behaviour.
- Preserve approval and monitoring choices. Writing a contract neither approves it nor enables usage monitoring or external filing.

## Output format

Return the requirement ID and statement, evidence with quote lineage, and confidence. Then a **Behaviour contract** section containing the promise, expectation table (metric ID, description, comparator, target, tolerance, unit), baseline source/values/note, events to instrument and weekly window rules. End with “Monitored version of this requirement's entry in Product Overview › Success Metrics.” Include the schema-shaped contract JSON separately, or an **Open loop / decisions needed** section when it cannot yet be grounded. Label synthetic examples as synthetic.
