# Persona review run (Pact addendum P5)

- **Date:** 2026-11-08
- **Model:** Claude Opus 5.5 (`claude-opus-5-5`), run as a fresh Claude Code agent with no context from the build session
- **Checkout:** `main` at `a598048` ("merge data: P4 pact skills"), in a separate clean worktree
- **Skill:** `skills/contract-persona-review`
- **Did it flag the C-01 second-tab problem?** Yes. It is the first finding: the prior-auth field sits on a hidden "Authorization" tab, so she types the number into Notes.

## Exact prompt

The addendum's prompt, preceded by two lines that pin the folder and keep the run read-only, and followed by one line asking for the report only:

```
Work only in the folder /Users/ak/Documents/Pro/VSWorkspace/Projects/HackUTD26/HackUTD2026-p5 (a checkout of main). Read files only; do not edit, create or delete anything, and do not run git commands that change state.

Use the skill in `skills/contract-persona-review` to review `server/static/claim.html` and `server/static/claim.js` against contracts C-01, C-03 and C-04. Write your report as the table the skill specifies.

Your final message must be the complete report exactly as you would hand it over (the table plus the sections the skill asks for after it), with nothing else before or after it.
```

## Output (unedited)

| Contract | What she'd hit | Her supporting quote | Severity | Suggested fix |
|---|---|---|---|---|
| C-01 | The prior-auth number field sits on a separate "Authorization" tab that is hidden by default (claim.html:61, `hidden`). When she picks "70553 · MRI, prior authorization required", nothing reveals the field or points her to it. The Notes textarea is right in front of her on Main, so she types "AUTH 48213..." or "AUTH SEE FAX" there as she always has. | "If it needs prior auth I put the number in the notes, or sometimes just 'see fax'." | high | Put the prior-auth field on Main and show it inline as soon as a procedure with `data-requires-prior-auth="true"` is selected, with no extra tab. |
| C-01 | Submit goes through with the auth field empty on a prior-auth procedure. claim.js:86 only records `first_pass_clean: false` and does not stop or warn her. The old habit still "works" from her side, so the 71% notes baseline would carry straight over and `pa_field_fill_rate` would fall well short of 0.95. | "Honestly we mostly just write 'see fax'." | high | When `requires_prior_auth` is true and the field is empty, show an inline prompt at submit that names the field and takes her to it. Ideally detect "AUTH"/digit patterns in notes client-side and offer to move the number into the field. |
| C-01 | `pa_in_notes_rate` can only be measured when `settings.notes_matching` is on (claim.js:87). With it off, `claim_submitted` has no `notes_patterns`, so her notes workaround goes unseen and the second C-01 metric can't be computed. The regex (claim.js:90) also needs 4 or more digits right after "auth"/"pa", so variants like "AUTH: see fax 482" or a number with a dash or space in it would be missed. | "If it needs prior auth I put the number in the notes, or sometimes just 'see fax'." | medium | Make the tag-only notes pattern check required for C-01 (or have the contract report "unmeasured" rather than pass when it is off). Widen the pattern to handle separators and test it against the legacy note samples. |
| C-03 | `claim_reopened` is never emitted, and `claim_id_hash` is a fresh `crypto.randomUUID()` on every page load (claim.js:6). Reopening a claim therefore looks like a brand-new claim, so `multi_reopen_rate` can't be computed and a breach would never show up. | "If I have to open a claim twice, something went wrong." | high | Derive `claim_id_hash` from a stable claim identifier (hashed). On load, emit `claim_reopened` when that claim was opened before and has not been submitted. |
| C-03 | Once submitted, the form locks (claim.js:83, 94). If the auth number was hidden on the other tab and she forgot it, or the payer kicks the claim back, she has to open the claim again to fix it. That reopen is the exact pattern the contract is meant to prevent, and it is most likely on her prior-auth claims, which are most of her day. | "If I have to open a claim twice, something went wrong." | medium | Catch missing required-by-procedure fields (the prior-auth number) before submit, inside the same sitting, so the fix doesn't need a second open. |
| C-04 | Nothing in the build handles coverage changes. There is no eligibility check action, no coverage-changed indicator, and no queue that sends these claims to her. The `coverage_changed` and `eligibility_checked` events are never emitted. She depends on the claim showing up in her queue (legacy RETRO-ELIG) and won't go looking for it, so re-checks inside 48 h would fall well below 0.90 and the contract can't be measured at all. | "Oh, that. If coverage changes after the visit, it lands in my queue and I re-run eligibility." | high | Bring the RETRO-ELIG behaviour back: put claims whose coverage changed after the date of service in her queue, flag them on the claim screen with a "Re-run eligibility" action in the main flow, and emit `coverage_changed` and `eligibility_checked`. |

Contracts kept: none. C-01, C-03 and C-04 each have at least one high-severity finding. The build does emit `claim_tab_viewed`, `ui_click`, `claim_opened` and `claim_submitted` with `prior_auth_number_filled`, so C-01's field fill rate itself is measurable.

Preferences (not contract breaks):
- The sidebar heading "One claim, two sections" and the copy saying authorization "has its own tab" present the split as a feature. For her, the tab is just an extra step.
- The "Notes" placeholder "Synthetic notes only" gives no hint that the auth number belongs somewhere else.
