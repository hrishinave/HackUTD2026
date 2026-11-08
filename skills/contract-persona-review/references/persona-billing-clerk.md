# Persona: Billing clerk 2 (interview INT-01)

Built only from `legacy/scripts/billing_clerk_2.md`, `kb/people.json` and contracts C-01, C-03 and C-04. Fictional, synthetic demo data. Use her exact quotes; never invent new ones.

## Who she is

- Billing clerk for 4 years at the clinic. Role: `billing_clerk`. Interviewed as INT-01.
- She handles most of the imaging claims, so prior authorization is a big part of her day.
- Friendly and talkative, but she describes what she does, not why.

## Goals

- Get each claim out the door correctly on the first try (C-03: finish a claim in one sitting without reopening it).
- Get prior-auth claims accepted. For her that has always meant "the auth goes in the notes".
- Handle claims whose coverage changed after the visit, which land in her queue (C-04).

## Daily volume

- "Pretty much every imaging claim for Medicare Advantage needs one." Prior-auth claims are routine for her, not an edge case, so any extra step on them is paid many times a day.

## Habits and workarounds

- **Auth number in the notes.** "If it needs prior auth I put the number in the notes, or sometimes just 'see fax'." and later "Honestly we mostly just write 'see fax'."
- **What she actually types** (from the facilitator notes): "AUTH SEE FAX" or "AUTH 48213...". The legacy rule PA-SCAN only accepted a prior-auth claim if the notes contained "AUTH". She has forgotten that the word "AUTH" is what mattered; to her it is just how you do it.
- **The PA-NUM field.** In the legacy app: "There's a field for it? I've never used it. The system doesn't care what's in there." She does not look for a dedicated auth field, because one never mattered.
- **Coverage changes.** She never brings this up on her own. Only when asked: "Oh, that. If coverage changes after the visit, it lands in my queue and I re-run eligibility." She relies on the claim showing up in her queue; she does not go looking for it.
- **Stuck claims.** "If a claim sits pending more than 30 days I phone the payer and write it on a sticky note." She tracks this outside the system.

## Where her patience runs out

- An extra tab or screen on every prior-auth claim. They are most of her imaging work, so she will fall back to the notes field she already knows if the new field isn't right in front of her.
- Having to reopen a claim to finish it. C-03's only quote (billing clerk 1's, but it is the team norm) is "If I have to open a claim twice, something went wrong."
- Anything that expects her to remember to re-check eligibility herself. If a coverage-change claim doesn't come to her, she won't notice it.

## The contracts she is held to

- **C-01 (R-01):** Every claim that needs prior authorization records the authorization number in its own field. Fill rate at least 0.95 (tolerance 0.05); auth number typed in notes at most 0.05 (tolerance 0.05). Legacy baseline: 71% put it in notes.
- **C-03 (R-03):** Clerks finish a claim in one sitting without repeatedly reopening it. Reopened more than once at most 0.10 (tolerance 0.05). Legacy baseline 0.06.
- **C-04 (R-04):** When coverage changes after the date of service, eligibility is re-checked before the claim goes out. Re-check within 48 h at least 0.90 (tolerance 0.10). Legacy baseline 0.83.
