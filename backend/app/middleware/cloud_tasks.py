"""Sprint C — Cloud Tasks request verifier.

Used as a FastAPI dependency on /internal/tasks/* endpoints. Three-step gate:

  1. Require X-CloudTasks-TaskName header. Cloud Tasks always sets this; no
     browser sends it. This alone defeats the most likely "user accidentally
     hits internal endpoint" path.

  2. Verify the Bearer OIDC token is a Google-issued ID token whose
     audience matches our worker URL (settings.runs_worker_url). The token's
     email claim is checked against settings.runs_worker_sa.

  3. In test/local mode (settings.dev_auth_bypass=true), skip OIDC verification
     but still require the X-CloudTasks-TaskName header. This lets tests exercise
     the worker endpoint without minting real Google tokens.
"""
from __future__ import annotations

import logging
import os

from fastapi import HTTPException, Request

from backend.app.config import settings

logger = logging.getLogger(__name__)


def verify_cloud_tasks_request(request: Request) -> None:
    """FastAPI dependency that gates internal endpoints to Cloud Tasks only."""
    task_name = request.headers.get("X-CloudTasks-TaskName")
    if not task_name:
        raise HTTPException(
            status_code=401,
            detail="Internal endpoint requires X-CloudTasks-TaskName header",
        )

    # Read env at request-time (not import-time) so tests + DEV bypass work
    # without depending on the Settings instance having seen the env var.
    if os.getenv("DEV_AUTH_BYPASS", "false").lower() == "true":
        logger.info("DEV_AUTH_BYPASS=true — skipping OIDC verification on internal endpoint")
        return

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token on internal endpoint")
    token = auth_header.removeprefix("Bearer ")

    try:
        from google.auth.transport import requests as g_requests
        from google.oauth2 import id_token
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail="google-auth not installed; cannot verify OIDC token",
        ) from exc

    try:
        # The audience of the OIDC token must match the URL Cloud Tasks targeted.
        # We accept either the absolute URL or any URL on the configured worker
        # host (Cloud Run can be reached via *.run.app and the project URL).
        info = id_token.verify_oauth2_token(token, g_requests.Request())
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail=f"OIDC token invalid: {exc}") from exc

    expected_sa = settings.runs_worker_sa
    if expected_sa and info.get("email") != expected_sa:
        raise HTTPException(
            status_code=403,
            detail=f"OIDC token email {info.get('email')!r} does not match {expected_sa!r}",
        )

    aud = info.get("aud", "")
    expected_url = settings.runs_worker_url.rstrip("/")
    if expected_url and not aud.startswith(expected_url):
        raise HTTPException(
            status_code=403,
            detail=f"OIDC audience {aud!r} does not match {expected_url!r}",
        )
