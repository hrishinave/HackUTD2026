# Fit Check v2 API reference

The v2 server is a FastAPI application normally run at `http://127.0.0.1:8000`.
All JSON endpoints return JSON unless noted. Authentication tokens come from the
server's `.env`; never put them in source control.

## Interview workflow

### `GET /api/interviews`

Lists saved and currently running interviews for the board selector. Each item
contains `interview_id`, `label`, `interviewee`, `started`, and `updated_at`.
An empty array is valid when no interview has been started or saved yet.

### `POST /api/interviews/{interview_id}/start`

Starts or restarts an interview session and saves its initial state. The ID must
follow the `INT-01` format.

Request body:

```json
{"interviewee": "billing_clerk_2"}
```

`interviewee` is optional; the server chooses the knowledge-base default for the
interview ID. A successful response includes `ok`, `interview_id`,
`interviewee`, and `warm_up`. Unknown interviewees return `404`.

### `GET /api/interviews/{interview_id}/state`

Returns the current transcript, played questions, queue, slot fills,
contradictions, coverage/yield values, and call counters. Returns `404` until
the interview has been started.

### `WebSocket /ws/client/{interview_id}`

The live interviewer transport. The client receives `queue`, `audio`, and
`ack` messages and may send:

- `{"type":"utterance","text":"...","final":true,"t_ms":1234}` to submit a final transcript sentence.
- `{"type":"played","question_id":"Q-1","t_ms":1234}` after playing a question.
- `{"type":"metric","name":"tap_to_audio_ms","value":123}` for telemetry.
- `{"type":"hello"}` or `{"type":"tap",...}` for connection/tap logging.

The socket can initialize a session automatically, but the board's v2 flow uses
the explicit start button first.

### `GET /api/contracts`

Returns the catalog behaviour contracts, including live evidence merged from
running `INT-NN` sessions and approved draft contracts.

## Board settings

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

### `POST /stub/v2/reporting-api/feedback`

Local Software Factory stand-in. Accepts a validated feedback payload and
returns an incrementing number such as `{"feedback_number":123}`. It never
connects to a real external service. Invalid payloads return `422`.

## Contract drafting

### `POST /api/drafts`

Drafts contracts and open loops from a saved interview. Request body:

```json
{"interview_id":"INT-01"}
```

Returns `interview_id`, draft `items`, and `rejected` checker results. A missing
saved interview returns `404`; a concurrent run returns `409`; a model/provider
failure returns `502`; malformed IDs return `422`.

### `GET /api/drafts`

Lists stored draft records. Optional query filters:

```text
/api/drafts?interview_id=INT-01&status=draft
```

### `POST /api/drafts/{draft_id}/approve`

Approves a draft and assigns final contract/requirement IDs where applicable.
Requires `X-Admin-Token`. Missing credentials return `401`, unknown drafts
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
- `GET /clips/{path}` — prepared/live audio clips under `data/clips`.
- `GET /docs`, `/redoc`, `/openapi.json` — FastAPI-generated API documentation.

The standalone `/interviewer` page was removed in v2. The interview UI is now
entered from the board's Interview tab; the interview API and WebSocket remain
available for the live transport.
