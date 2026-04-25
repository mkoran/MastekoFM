# Sprint C — Async runs via Cloud Tasks

> Estimated: ~4-5 days
> Branch: `epic/sprint-c-async`
> Goal: POST /api/runs returns 202 immediately; worker processes in background; UI polls live status.
> Blocked-by: Sprint B
> Blocks: Sprint G (sweeps need async)

---

## Why

The synchronous Calculate from v1 blocks for ~17s on Campus Adele. For Sprint G's sensitivity sweeps (50+ runs in parallel) and the spec's "100+ concurrent" requirement, we need async execution. This is the foundation.

---

## Definition of Done

- POST /api/runs returns 202 in <500ms with `{run_id}`
- A separate Cloud Run service `masteko-fm-worker-dev` processes runs from Cloud Tasks queue `mfm-runs-dev`
- Worker handles 5 concurrent Hello World runs without errors
- Frontend shows live status updates (Firestore onSnapshot or 2s poll)
- Failed runs retry automatically (3 attempts, exponential backoff)
- User can cancel a pending Run via UI
- User can manually retry a failed Run via UI (creates new Run with same composition)
- Cloud Tasks OIDC verified at the worker endpoint (rejects Firebase tokens)

---

## Stories

### C-001 · Cloud Tasks queues (S)

`scripts/create_queues.sh`:
```bash
gcloud tasks queues create mfm-runs-dev --location=northamerica-northeast1 \
  --max-attempts=3 --min-backoff=30s --max-backoff=300s
gcloud tasks queues create mfm-runs-prod --location=northamerica-northeast1 \
  --max-attempts=3 --min-backoff=30s --max-backoff=300s
```

### C-002 · Worker Cloud Run service (S)

Same Docker image as the API but with a different `--command`:
- API: `uvicorn backend.app.main:app --host 0.0.0.0 --port 8080`
- Worker: `uvicorn backend.app.workers.main:app --host 0.0.0.0 --port 8080`

The worker runs a minimal FastAPI app exposing only `/internal/tasks/run/{run_id}`.

`deploy-dev.sh` deploys both services from one image build.

### C-003 · Internal worker endpoint (S)

`backend/app/workers/main.py` + `backend/app/workers/run_handler.py`:

```python
@app.post("/internal/tasks/run/{run_id}")
async def handle_run_task(run_id: str, oidc_token: VerifiedOIDC = Depends(verify_oidc)):
    """Cloud Tasks calls this with an OIDC token. Firebase tokens are rejected."""
    run_doc = get_firestore_client().collection(...).document(run_id).get()
    if not run_doc.exists:
        return {"status": "skipped", "reason": "run not found"}
    
    run = run_doc.to_dict()
    
    # Idempotency: if already done/cancelled, ack and return
    if run["status"] in ("completed", "failed", "cancelled"):
        return {"status": "skipped", "reason": f"already {run['status']}"}
    
    # Cancellation check
    if run["status"] == "cancelled":
        return {"status": "skipped", "reason": "cancelled"}
    
    # Mark running
    run_doc.reference.update({"status": "running", "started_at": now()})
    
    try:
        result = run_executor.execute_run_sync(...)
        run_doc.reference.update({"status": "completed", ...result})
    except Exception as e:
        run_doc.reference.update({"status": "failed", "error": str(e)})
        raise  # let Cloud Tasks retry
```

OIDC verifier checks `iss=https://accounts.google.com` and `email=<service-account>@masteko-fm.iam.gserviceaccount.com`.

### C-004 · POST /api/runs enqueues (S)

Update `routers/runs.py`:
```python
@router.post("/api/runs", status_code=202)
async def create_run(body: RunCreate, current_user: CurrentUser):
    # Validate composition
    errors = run_validator.validate(...)
    if errors:
        raise HTTPException(400, {"errors": errors})
    
    # Create Run doc with status=pending
    run_ref = db.collection("runs").document()
    run_ref.set({"status": "pending", ..., "triggered_by": current_user["uid"]})
    
    # Enqueue Cloud Task
    task = {
        "http_request": {
            "http_method": "POST",
            "url": f"{WORKER_URL}/internal/tasks/run/{run_ref.id}",
            "oidc_token": {"service_account_email": SERVICE_ACCOUNT_EMAIL},
        }
    }
    tasks_client.create_task(parent=QUEUE_PATH, task=task)
    
    return {"run_id": run_ref.id, "status": "pending"}
```

### C-005 · Worker handler (S)
See C-003.

### C-006 · Cloud Tasks retry config (XS)
Set on queue creation (C-001). Verify in Cloud Console.

### C-007 · Frontend polling (S)

Frontend uses Firestore onSnapshot to subscribe to the Run doc:
```typescript
const unsub = onSnapshot(doc(db, "runs", runId), (snap) => {
  setRun(snap.data())
  if (snap.data().status === "completed" || snap.data().status === "failed") {
    unsub()
  }
})
```

This requires Firestore security rules to allow read on `runs/{id}` for the run's `triggered_by` user (or project members).

### C-008 · Cancel button (XS)
`POST /api/runs/{id}/cancel` sets status=cancelled. Worker checks before each major step.

### C-009 · Retry button (XS)
`POST /api/runs/{id}/retry` creates a new Run with same composition + `retry_of` field pointing at the original.

### C-010 · Worker IAM (S)
Service account `masteko-fm-worker-{env}@masteko-fm.iam.gserviceaccount.com` with:
- `roles/datastore.user` (Firestore)
- `roles/storage.objectAdmin` on bucket `masteko-fm-outputs`
- Drive scope via Workload Identity (worker uses same OAuth token as user) — TBD design

### C-011 · Tests (M)
- Mock Cloud Tasks client; assert task creation with correct URL + OIDC config
- Integration test (using fake/in-memory queue): POST /api/runs → worker pulls → execution → status update
- Test cancellation race
- Test retry on transient failure

### C-012 · Deploy script update (S)
`deploy-dev.sh` deploys both services from one image. Add second `gcloud run deploy` block.

### C-013 · Smoke test (XS)
Launch 5 concurrent Hello World runs. Verify all complete within 10s. Check Cloud Logging for any errors.

---

## Risks

| Risk | Mitigation |
|---|---|
| Cloud Tasks delivers same task twice | Idempotency check at start of handler |
| Worker container OOMs on Campus Adele | Same Dockerfile + LibreOffice; should match API behavior. Set memory ≥ 2GB. |
| OIDC verification too strict (rejects valid tokens) | Test with explicit gcloud-generated OIDC tokens before deploying |
| Drive token expiry mid-run | Worker re-fetches Drive credentials per run; long-lived runs (>1h) need refresh logic — defer to Sprint G |
| Firestore listener costs spike | Each poll opens a transient listener; close on completed/failed |
