# Behaviour contract anti-patterns

Each of these makes a contract unverifiable or a finding untrustworthy. Reject or fix them.

1. **Numbers invented in the interview.** A target the interviewee guessed ("maybe four minutes") is evidence, not a target. Set the target from legacy log facts or the stated need, and record the quote as evidence. If the logs disagree with the quote, that is a say-vs-do gap: note it in `confidence`, do not average them.
2. **No tolerance.** Every expectation needs `tolerance`. Without it, one noisy week reads as a broken promise. Breach is beyond the tolerance; broken is beyond twice the tolerance.
3. **Free-text events.** Signals must come from typed events with flags and tags (`claim_submitted.prior_auth_number_filled`, `notes_pattern:auth_number`), never from storing or reading raw note text. Free text carries PHI and cannot be compared week to week.
4. **Findings without a contract ID or a quote.** A drift finding must name the contract it breaks and trace to the interview quote that created the requirement (lineage). A finding with neither is a hunch.
5. **Contracts for things usage can't show.** Trust, satisfaction and phone calls leave no event. Make them open loops with a suggested human check or an event to instrument, not contracts with made-up proxies.
6. **No privacy floor.** A window with fewer than `min_people` people or `min_tasks` tasks must be suppressed, not reported.
7. **No learning period.** The first weeks after launch are noise. Never call drift inside `learning_period_weeks`.
8. **Drift from one bad week.** Drift needs `consecutive_breaches_for_drift` breached weeks in a row.
9. **Effectors.** A contract observes. It never changes the system, blocks a user or files work without a human approving it.
