# Sprint C — Async runs via Cloud Tasks

> Status: ✅ shipped (code) on `epic/sprint-b-cleanup`. Full async mode requires
> running `./scripts/infra/setup_runs_queue.sh dev` once to create the queue +
> SA + IAM bindings. Without that one-time setup, the API runs in SYNC-THREAD
> fallback mode (still returns 202; thread executes in-process).
>
> Branch: `epic/sprint-b-cleanup`

## Why

Sprint A's `POST /api/runs` was synchronous: the HTTP request thread held
open until the engine finished. That's ~2s for Hello World, ~17s for Campus
Adele, and would scale linearly worse for larger Models. Two failure modes
this enables:
  1. Cloud Run request timeout (default 5min) → user sees a cancelled HTTP
     request even though the engine might still be running.
  2. Concurrent-request flooding holds threads, evicting other API calls.

Sprint C decouples the HTTP turn-around from the compute by:
  - POST /api/runs persists `status=pending` and **enqueues a Cloud Tasks task**.
    Returns 202 in <100ms.
  - Cloud Tasks delivers an OIDC-signed POST to `/internal/tasks/run/{run_id}`
    on the same Cloud Run service.
  - The worker handler pulls the Run from Firestore, executes, and updates
    the doc with terminal status.
  - Frontend polls `GET /api/runs/{id}` every 2s while pending/running.

## Why same Cloud Run service (not a separate worker)

MastekoFM compute is bounded (<30s today) and not high-volume (one Run per
user click). A separate worker service would double the deployment surface
without buying anything for current traffic. The internal endpoint can be
peeled off into its own service later — the Cloud Tasks contract stays
identical (just point `RUNS_WORKER_URL` at the new service URL).

## Sync-thread fallback (the killer feature)

If `RUNS_QUEUE` env var is empty, `services/run_queue.py:enqueue_run()` returns
`None` and the router launches the same worker function in a background
thread. The HTTP contract (POST returns 202) is identical. This means:
  - **Local dev** works without ever creating a queue.
  - **First DEV deploy of Sprint C** doesn't break — runs still execute
    in-thread until you flip the env vars.
  - **Tests** stay fast — no Cloud Tasks dep at import time.

## Stories

| ID | Story | Status |
|---|---|---|
| C-01 | Refactor execution into `routers/_run_worker.execute_run_by_id()` | ✅ |
| C-02 | New `services/run_queue.py` adapter (Cloud Tasks + sync-thread) | ✅ |
| C-03 | New `middleware/cloud_tasks.py` OIDC verifier (with DEV bypass) | ✅ |
| C-04 | `/api/runs` returns 202 with status=pending; persists Drive token | ✅ |
| C-05 | New `/internal/tasks/run/{id}` worker endpoint | ✅ |
| C-06 | RunResponse: enqueued_at, running_at, attempts, task_name | ✅ |
| C-07 | Frontend RunDetailPage polls every 2s while non-terminal | ✅ |
| C-08 | NewRunModal: "Launching…" instead of "Running… (~2-20s)" | ✅ |
| C-09 | `scripts/infra/setup_runs_queue.sh` — one-time per-env setup | ✅ |
| C-10 | Idempotent worker (Cloud Tasks may retry) — terminal runs skip | ✅ |
| C-11 | Drive token persisted on Run doc (Firestore encryption-at-rest) | ✅ |
| C-12 | Pytest: worker idempotency + happy + failure + endpoint gating | ✅ |
| C-13 | Run e2e smoke against DEV in async mode | 🔒 needs queue setup |
| C-14 | Run e2e smoke against PROD in async mode | 🔒 needs queue setup + Firebase auth |

## Test count delta
- Before: **88/88** (post INFRA-002)
- After: **94/94** (+3 worker + +6 router/internal)

## Auth model on `/internal/tasks/run/{id}`

Three-step gate (defense in depth):
  1. **X-CloudTasks-TaskName header** must be present. Cloud Tasks always sets
     this; browsers/curl callers don't. This alone defeats most accidental hits.
  2. (Skipped if DEV_AUTH_BYPASS=true.) Bearer OIDC token verified against
     Google's public keys. Email claim must match `RUNS_WORKER_SA`.
  3. (Skipped if DEV_AUTH_BYPASS=true.) Audience claim must start with
     `RUNS_WORKER_URL`.

A regular Firebase ID token rejected at step 2 (wrong issuer).

## Drive token handling

The user's `X-MFM-Drive-Token` is persisted on the Run doc when POST /api/runs
fires. The worker reads it from either:
  - The Cloud Tasks body (preferred — fresh from the user's session)
  - The Run doc (fallback for retries)

Cleared on terminal status so it doesn't sit in Firestore longer than needed.

⚠ Token TTL is ~1h from Google's issue time. Runs that take >55min from
   POST → execution will fail to read Drive-backed Models / packs / templates.
   Mitigations not yet implemented (would be V2):
     - Service-account delegation (no token TTL)
     - KMS-encrypted token + refresh-on-execute

## Marc's one-time setup per env

```bash
./scripts/infra/setup_runs_queue.sh dev      # creates queue + SA + IAM + flips env vars
./scripts/infra/setup_runs_queue.sh prod     # same for PROD
```

Until that runs, the deployed service stays in sync-thread mode (works fine,
just doesn't get the queue's retry / backoff / observability).

## Future work

- KMS-encrypt the persisted Drive token
- Cancellation endpoint (`POST /api/runs/{id}/cancel`)
- Run timeout enforcement on the worker side
- Live status via Firestore onSnapshot (kill the polling)
- Separate worker Cloud Run service when concurrent volume justifies it
