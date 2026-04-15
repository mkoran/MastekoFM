"""Firebase Auth middleware with DEV bypass."""
import os
from typing import Any

from fastapi import HTTPException, Request


def get_current_user(request: Request) -> dict[str, Any]:
    """Extract and verify the current user from the request."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header.removeprefix("Bearer ")

    if os.getenv("DEV_AUTH_BYPASS", "false").lower() == "true" and token.startswith("dev-"):
        email = token.removeprefix("dev-")
        return {"uid": f"dev-{email}", "email": email}

    # TODO: Firebase Auth token verification (Sprint 1)
    raise HTTPException(status_code=401, detail="Token verification not yet implemented")
