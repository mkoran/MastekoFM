"""Sprint C — Cloud Tasks adapter for async Run execution.

Two modes:
  - SYNC mode (settings.runs_queue empty): the API thread runs the executor
    inline. This is the Sprint A path; kept for local dev + tests.
  - ASYNC mode (settings.runs_queue set): /api/runs persists the Run + enqueues
    a Cloud Tasks task. The task POSTs to /internal/tasks/run/{id} on the
    same Cloud Run service, which pulls the Run from Firestore and executes.

Why same service (not separate worker): MastekoFM's compute is
  - bounded (~30s for Hello World, ~17s for Campus Adele today)
  - not high-volume (one Run per user click)
  - shares the same dependencies (LibreOffice already in the API image)
A separate worker service buys little and doubles the deployment surface.
If volume grows, the internal endpoint can be split into its own service
later — the queue + handler contract stays identical.

Auth on the internal endpoint:
  Cloud Tasks invokes with an OIDC token whose audience = the worker URL.
  The endpoint verifies (a) Cloud Tasks set X-CloudTasks-TaskName (browsers
  cannot), (b) the Bearer token is a valid Google-issued OIDC token for our
  service-account email. See backend/app/middleware/cloud_tasks.py.
"""
from __future__ import annotations

import json
import logging

from backend.app.config import settings

logger = logging.getLogger(__name__)


def is_async_enabled() -> bool:
    """True if Cloud Tasks is configured. False = SYNC fallback path."""
    return bool(settings.runs_queue and settings.runs_worker_url and settings.runs_worker_sa)


def enqueue_run(
    run_id: str,
    *,
    drive_token: str | None = None,
) -> str | None:
    """Enqueue a Cloud Tasks task that will POST /internal/tasks/run/{run_id}.

    Returns the task name (full GCP resource path) on success, or None if
    Cloud Tasks is not configured (caller should fall back to sync execution).

    The drive_token, if provided, is delivered as a body field to the worker
    so the worker can read Drive-backed Models / packs / templates with the
    same access the requester had. Persisted on the Run doc by the caller for
    auditability + idempotency on retry.
    """
    if not is_async_enabled():
        logger.info("Cloud Tasks not configured (runs_queue empty) — sync mode")
        return None

    # Lazy import to keep tests fast and avoid hard dep when not needed.
    from google.cloud import tasks_v2

    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(settings.gcp_project, settings.gcp_region, settings.runs_queue)

    payload = {"run_id": run_id}
    if drive_token:
        payload["drive_token"] = drive_token

    target_url = f"{settings.runs_worker_url.rstrip('/')}/internal/tasks/run/{run_id}"
    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": target_url,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(payload).encode(),
            "oidc_token": {
                "service_account_email": settings.runs_worker_sa,
                "audience": target_url,
            },
        }
    }

    response = client.create_task(parent=parent, task=task)
    logger.info("Enqueued task %s for run %s", response.name, run_id)
    return response.name


def execute_in_thread(run_id: str, drive_token: str | None) -> None:
    """Sync-mode fallback: run the executor in a background thread.

    The HTTP request returns 202 immediately (matching the async-mode contract);
    the actual computation happens in the thread. Status updates land on the
    Run doc the same way the worker would do them.

    This lets us keep the SAME router contract (POST /api/runs returns 202
    with run_id) regardless of whether Cloud Tasks is configured. Local dev,
    tests, and "I haven't created the queue yet" all work without code changes.
    """
    import threading

    from backend.app.routers import _run_worker  # local import — avoids cycle

    def _run():
        try:
            _run_worker.execute_run_by_id(run_id, drive_token=drive_token)
        except Exception:  # noqa: BLE001 — top of background thread
            logger.exception("Sync-thread executor crashed for run %s", run_id)

    threading.Thread(target=_run, name=f"run-{run_id[:8]}", daemon=True).start()


# ── Helpers for tests ────────────────────────────────────────────────────────


def fake_enqueue_inline(run_id: str, *, drive_token: str | None = None) -> str:
    """Test helper: pretend to enqueue, but execute inline. Used in tests that
    want the full pipeline without spinning up a thread."""
    from backend.app.routers import _run_worker

    _run_worker.execute_run_by_id(run_id, drive_token=drive_token)
    return f"projects/test/locations/test/queues/test/tasks/{run_id}"
