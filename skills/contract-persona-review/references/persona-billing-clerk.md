# Billing clerk 2: evidence-grounded persona

Synthetic demo persona. Sources only: `legacy/scripts/billing_clerk_2.md`, `kb/people.json` (`billing_clerk_2`), and C-01, C-03 and C-04 in `contracts/medicare_contracts.json`. UI implementation details are deliberately outside this persona.

## Goals and work

- Billing clerk for four years; handles most imaging claims. Prior authorization is a large part of her day (role-play script).
- Role: billing_clerk; label: Billing clerk 2; interview INT-01. Relevant contracts: C-01, C-04, C-03 (`kb/people.json`).
- Goals grounded in those contracts: record required authorization, complete claims in one sitting, and re-check eligibility when coverage changes after a visit.
- Daily claim volume is **not specified** in these sources. “Pretty much every imaging claim for Medicare Advantage needs one” describes authorization frequency, not a numerical daily workload (C-01, INT-01 14:51, Q-14).
- Friendly and talkative; describes what she does rather than why (script). Do not infer computer literacy, reading speed or an attention-span threshold.

## Habits and workarounds

- Her own quote: “If it needs prior auth I put the number in the notes, or sometimes just 'see fax'.” (C-01, INT-01 14:32, Q-12.)
- Her own script statement: “Honestly we mostly just write 'see fax'.” This conflicts with clerk 1's account; retain the disagreement.
- Facilitator context from the script: she types “AUTH SEE FAX” or “AUTH 48213...” because PA-SCAN returns claims without “AUTH” in notes. She has forgotten that this keyword is what matters. This is contextual evidence, not an interview quote from her.
- If asked about the legacy PA-NUM field: “There's a field for it? I've never used it. The system doesn't care what's in there.” (Script; no timestamp or question ID supplied.) This supports investigating discoverability and the familiar notes workaround, without assuming any particular new UI defect.
- Coverage changes are not volunteered. Her own quote: “Oh, that. If coverage changes after the visit, it lands in my queue and I re-run eligibility.” (C-04, INT-01 21:05, Q-19.)
- If asked about pending claims: “If a claim sits pending more than 30 days I phone the payer and write it on a sticky note.” (Script; no timestamp/question ID supplied.) No event records payer calls; this is an open loop, not a measurable contract in this review.

## Promises and friction to assess

- **C-01 / R-01:** Every claim needing prior authorization records its number in its own field. Field-fill target >= 0.95 with 0.05 tolerance; auth-in-notes target <= 0.05 with 0.05 tolerance. Her old workaround is notes or “see fax”; inspect whether the new path makes the dedicated field usable and discoverable.
- **C-03 / R-03:** Finish claims in one sitting without repeated reopens. Multi-reopen share <= 0.10, tolerance 0.05. Its quote is **Billing clerk 1's**, not hers: “If I have to open a claim twice, something went wrong.” (INT-02 09:44, Q-05.) It is role-level supporting evidence; do not attribute it to clerk 2.
- **C-04 / R-04:** Re-check eligibility after post-visit coverage changes before the claim goes out. Recheck-within-48-hours share >= 0.90, tolerance 0.10. Her current queue is the cue to re-run eligibility.
- These sources do not specify where her patience “runs out” numerically. Supported friction is a workflow that restores the old authorization workaround, forces repeated reopenings (role-level C-03 evidence), or loses the queue cue for eligibility. Do not invent an emotional reaction or a new quote.

## Evidence limits

All targets, quotes and baselines in this demo are planted synthetic values. Review code to identify supported contract risks; neither this persona nor a walkthrough establishes a real weekly breach or an actual observed abandonment rate.
