# Pact v2 API reference

The v2 server is a FastAPI application normally run at `http://127.0.0.1:8000`.
All JSON endpoints return JSON unless noted. Authentication tokens come from the
server's `.env`; never put them in source control.

## Interview workflow

### `GET /api/interviews`

Lists saved and currently running interviews for the board selector. Each item
contains `interview_id`, `label`, `person_name`, `position`, `company_id`,
`company_name`, `interviewee`, `started`, and `updated_at`. An empty array is
valid when no interview has been started or saved yet.

### `GET /api/interviews/next-id`

Returns the next unused interview ID: one more than the highest `INT-NN` found
in saved states (`data/state/INT-*.json`) and running sessions, zero-padded to
at least two digits.

```json
{"interview_id": "INT-08"}
```

`INT-01` when nothing exists yet; after `INT-99` comes `INT-100`. The board
should call this before `POST /api/interviews/{id}/start`.

### `GET /api/interview-options`

Companies for the board's start dialog:

```json
{"companies": [
  {"id": "medicare_billing_demo", "name": "Medicare Billing Office",
   "people": [{"id": "billing_clerk_2", "label": "Billing clerk 2", "role": "billing_clerk", "interview_id": "INT-01"}]},
  {"id": "acme_logistics", "name": "Acme Logistics",
   "people": [{"id": "dana_lee", "label": "Dana Lee", "role": "Dispatcher", "interview_id": "INT-05"}]}
]}
```

The built-in demo company always comes first with its knowledge-base people.
Every other company found in saved or running interviews follows (deduplicated
by `company_id`, sorted by name), listing the people interviewed there; for
those, `role` is the position that was entered.

### `POST /api/interviews/{interview_id}/start`

Starts or restarts an interview session and saves its initial state. Use an ID
from `GET /api/interviews/next-id` (`INT-` and two or more digits).

Request body (all fields optional):

```json
{"company_id": "acme_logistics", "company_name": "Acme Logistics",
 "person_name": "Dana Lee", "position": "Dispatcher"}
```

- Demo company (`company_id` omitted or `"medicare_billing_demo"`): the
  interviewee comes from `interviewee` (a `kb/people.json` key) or the
  knowledge-base default for the interview ID; unknown interviewees return
  `404`. The brief carries the Medicare context (rule catalogue, contract
  slots, doc diffs, log facts, open items). `person_name` and `position` are
  optional overrides for display.
- Any other company: the person comes from the body; `interviewee` is ignored
  and never causes a `404`. The brief is generic (no Medicare material) and
  built from the company name, person name and position; there are no contract
  slots, so `coverage` stays `0`.

Every question is written by Claude Haiku (`bank_id` is always `null`; there is
no prepared question bank). After the prompt-cache warm-up the server asks Haiku
for opening questions on the empty transcript and queues them; if that fails or
times out (8 s), the first fallback-plan question is queued instead (for other
companies the plan is generic, e.g. "Walk me through a typical day as
Dispatcher.").

Response:

```json
{"ok": true, "interview_id": "INT-08", "interviewee": "dana_lee",
 "company_id": "acme_logistics", "company_name": "Acme Logistics",
 "person_name": "Dana Lee", "position": "Dispatcher",
 "warm_up": "ok", "opening": "ok"}
```

`opening` is `"ok"` (Haiku questions queued), `"plan"` (no questions returned,
fallback plan queued) or `"failed: <Error>"`.

### `GET /api/interviews/{interview_id}/state`

Returns the current transcript, played questions, queue, slot fills,
contradictions, coverage/yield values, and call counters, plus `company_id`,
`company_name`, `person_name`, `position` and `label`. Returns `404` until the
interview has been started.

### `GET /api/interviews/{interview_id}/transcript`

The interview as Markdown (`text/markdown; charset=utf-8`), for download. Works
for running sessions (in memory) and saved ones (`data/state`); unknown IDs
return `404`. Shape:

```markdown
# Interview INT-09: Prakrit Chauhan, software engineer at randstad technology solutions

- Company: randstad technology solutions
- Person: Prakrit Chauhan
- Position: software engineer
- Interview: INT-09

## Transcript

[00:42] fixing up the Cobalt Scripts
[00:53] Q-13 asked: Detail: How long does one of those old, slow Cobalt scripts take to run?
[01:16] that usually takes about 20 minutes for that script to run ...

## Contradictions

- person_vs_self: "statement a" vs "statement b"
```

Transcript lines and played questions are interleaved in time order (a
question played at the same mm:ss as a line comes after it); each line ends in
two spaces (a Markdown line break). With no lines yet the transcript section
says `_No transcript yet._`. The contradictions section only appears when there
are any; a rule ID, when present, follows the kind in parentheses.

### `WebSocket /ws/client/{interview_id}`

The live interviewer transport. The client receives `queue`, `audio`, and
`ack` messages and may send:

- `{"type":"utterance","text":"...","final":true,"t_ms":1234}` to submit a final transcript sentence.
- `{"type":"played","question_id":"Q-1","t_ms":1234}` after playing a question.
- `{"type":"metric","name":"tap_to_audio_ms","value":123}` for telemetry.
- `{"type":"hello"}` or `{"type":"tap",...}` for connection/tap logging.

The socket can initialize a session automatically, but the board's v2 flow uses
the explicit start button first.

### `GET /api/contracts?company_id=`

Contracts are per company.

- No `company_id`, or `medicare_billing_demo`: the Medicare catalog contracts
  (C-01..C-05) with live evidence merged from running demo-company `INT-NN`
  sessions, plus approved drafted contracts whose `company_id` is the demo
  company or missing (unchanged from before).
- Any other company: only that company's approved drafted contracts (no
  catalog contracts, no live merge); `[]` when it has none.

Every contract may carry an optional `company_id`; approved drafts always do.
Contract IDs (`C-NN`) and requirement IDs (`R-NN`) are global across companies.

## Board settings

Settings, drift, findings, filing and lifecycle routes all take an optional
`?company_id=` query parameter. Without it they use the default client files
(`data/client_settings.json`, `data/live_events.jsonl`,
`data/filed_feedback.json`); with it they use
`data/clients/<company_id>/...` so each company has its own settings, events
and filing record.

They also measure only that company's contracts (the same set as
`GET /api/contracts?company_id=`): without `company_id` or with the demo
company, the Medicare catalog plus demo approved contracts; for any other
company, only its own approved contracts. Drift for another company is simply
empty until that company sends events, and
`/api/contracts/{id}/sf-requirement` returns `404` for a contract that belongs
to a different company than the one asked for. Approving a contract for a
non-demo company adds it to that company's `contracts_watched`
(`data/clients/<company_id>/client_settings.json`); demo approvals still go to
the default settings file.

### `GET /api/settings`

Returns current settings plus the latest 20 audit entries. Important fields are
`drift_enabled`, `contracts_watched`, `notes_matching`, `send_to_sf`,
`retention_days`, and `admin`.

### `POST /api/settings`

Updates settings. Requires the `X-Admin-Token` header matching `ADMIN_TOKEN`.
Only changed fields need to be sent.

Example:

```json
{"drift_enabled": true, "contracts_watched": ["C-01", "C-02"]}
```

Use `{"drift_enabled":false,"purge":true}` to turn monitoring off and purge
stored live events. Invalid values return `422`; a missing or incorrect token
returns `401`.

## Drift and findings

### `GET /api/drift`

Returns `{"enabled":false}` when monitoring is off. When enabled, returns
weekly measurements, targets, tolerance, learning periods, status, breach week,
severity, and recovery state for watched contracts.

### `GET /api/findings`

Returns drifting/broken findings for watched contracts. Each finding includes
status, weekly values, first breach, severity, estimated weekly cost, type and
reason, related signals, explanation, and interview lineage.

### `GET /api/findings/{finding_id}/sf-payload`

Builds the exact simulated Software Factory feedback JSON for a finding.
Requires `send_to_sf` to be enabled; otherwise returns `403`. Unknown findings
return `404`.

### `POST /api/findings/{finding_id}/file?company_id=`

Files a finding to the local Software Factory stub once per company and
returns `{"feedback_number": 123, "already_filed": false, "payload": {...}}`;
filing again returns the same number with `already_filed: true`. Requires that
company's `send_to_sf`; otherwise `403`. Unknown findings return `404`.

### `GET /api/filed?company_id=`

The company's filing record: `{finding_id: {"feedback_number", "contract_id",
"filed_at"}}`, `{}` when nothing is filed. Filing `F-01` for one company does
not mark it filed for another.

### `GET /api/lifecycle?company_id=`

Stage of every contract and pending draft (`drafted`, `approved`, `baselined`,
`kept`/`broken`, `renegotiated`) using that company's settings, events and
filing record.

### `GET /api/contracts/{contract_id}/sf-requirement?company_id=`

Software Factory requirement document (Markdown) for one contract; when that
company's drift monitoring shows the contract broken, the document includes a
simulated proposed change. Unknown contracts return `404`.

### `POST /stub/v2/reporting-api/feedback`

Local Software Factory stand-in. Accepts a validated feedback payload and
returns an incrementing number such as `{"feedback_number":123}`. It never
connects to a real external service. Invalid payloads return `422`.

## Contract drafting

### `POST /api/drafts`

Drafts contracts and open loops from one interview, running or saved (a
running session's in-memory state is used, so the board can call this the
moment an interview ends). Request body:

```json
{"interview_id":"INT-09"}
```

Response:

```json
{"interview_id": "INT-09", "company_id": "randstad_technology_solutions", "mode": "generic",
 "items": [{"draft_id": "DR-INT-09-1", "kind": "contract", "status": "draft", "company_id": "...",
            "contract": {...}, "open_loop": null, "stated_value": 1200, "baseline_value": null,
            "target_source": "stated", "contradiction": null, "checks": [...], "rationale": "..."}],
 "rejected": [{"requirement": "...", "reasons": ["quote not found in transcript"]}]}
```

`items` is the interview's records after the run (earlier approved/rejected
ones are kept, earlier pending drafts are replaced). Errors:

| Status | `detail` / body | When |
|---|---|---|
| `422` | `"interview_id must look like INT-01"` | malformed ID |
| `404` | `"no saved interview state for INT-NN"` | neither running nor saved |
| `422` | `"no transcript yet"` | the transcript has no non-blank lines |
| `409` | `"already drafting INT-NN"` | a run for the same interview is in flight |
| `502` | `{"error": "drafting failed: ..."}` | model refused, was cut off or failed |

Two modes, chosen from the interview's `company_id` (`mode` in the response):

- `demo` (`medicare_billing_demo` or no company): unchanged. Medicare prompt,
  events/flags/tags must exist in the event catalog, roles are the four
  Medicare roles, baselines come from the simulated legacy logs, rule IDs from
  the COBOL rule list.
- `generic` (any other company): the prompt names the company and position
  and has no Medicare text. There is no event catalog, so the model proposes
  the events the new system must emit (same six templates); code checks every
  event, flag, tag and source-view name against `^[a-z][a-z0-9_]{2,60}$`.
  `role` is a snake_case slug of the position (`"Software Engineer"` ->
  `software_engineer`). With no legacy logs, `baseline.source` is
  `"interview"` and `baseline.values` holds the interviewee's stated number
  (empty when none); confidence is `said: true, did: false, code: false`,
  level `medium` when the interviewee gave a number and `low` otherwise;
  `code_refs` is empty. A stated number becomes a contract (e.g. "takes about
  20 minutes ... down to 3 minutes" -> `median_duration`, stated 1200 s,
  target 180 s, tolerance 45 s); a real need with no measurable events
  becomes an open loop with a suggested snake_case event.

Both modes check quotes verbatim against the transcript (a single line, or up
to 4 consecutive speech fragments joined, with the same 0.85 fuzzy ratio),
check duplicates against that company's contracts only, and keep at most 5
drafts and 5 open loops. With `LLM_PROVIDER=fake` a generic interview gets one
open loop quoting its longest line.

### `GET /api/drafts`

Lists stored draft records. Optional query filters:

```text
/api/drafts?interview_id=INT-01&status=draft&company_id=randstad_technology_solutions
```

`company_id` keeps only drafts from that company's interviews (each record's
`company_id`, else its interview's saved state; unknown interviews count as
the demo company). Without `company_id` every draft is returned, as before.

### `POST /api/drafts/{draft_id}/approve`

Approves a draft and assigns final contract/requirement IDs where applicable.
The approved contract or open loop gets the draft's `company_id`. Requires
`X-Admin-Token`. Missing credentials return `401`, unknown drafts
return `404`, and already-decided/conflicting drafts return `409`.

### `POST /api/drafts/{draft_id}/reject`

Rejects a draft while preserving its record. Requires `X-Admin-Token`.
Optional body:

```json
{"reason":"Needs a human workflow review"}
```

## Usage events and simulation

### `POST /api/events`

Accepts one catalog-only usage event. Requires `X-Client-Token` matching
`CLIENT_WRITE_TOKEN` and enabled monitoring. Monitoring off returns `403`; bad
tokens return `401`; invalid event shapes or prohibited note/text content return
`422`.

### `GET /api/events/recent`

Returns the most recent 50 stored usage events. This endpoint does not expose
raw claim notes or free-text claim contents.

### `POST /api/simulate`

Regenerates synthetic legacy and post-launch data. Requires `X-Admin-Token`.
Optional body: `{"seed":7}`. Returns generated counts; bad credentials return
`401`.

### `GET /api/eval`

Scores saved interviews against the planted answer key: interviews, rules found,
hidden-rule discovery, contradiction matches, uncovered requirements, and draft
classification.

## HTML and static resources

- `GET /board` — v2 evidence board. Interview selection and starting now happen here.
- `GET /claim` — claim-screen HTML with the configured client token injected; returns `503` if the client token is missing.
- `GET /terms` — terms page.
- `GET /privacy` — privacy page.
- `GET /static/{path}` — static assets under `server/static`.
- `GET /clips/{path}` — live question audio clips under `data/clips`.
- `GET /docs`, `/redoc`, `/openapi.json` — FastAPI-generated API documentation.

The standalone `/interviewer` page was removed in v2. The interview UI is now
entered from the board's Interview tab; the interview API and WebSocket remain
available for the live transport.
