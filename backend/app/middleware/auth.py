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

    # DEV bypass
    if os.getenv("DEV_AUTH_BYPASS", "false").lower() == "true" and token.startswith("dev-"):
        email = token.removeprefix("dev-")
        return {"uid": f"dev-{email}", "email": email, "display_name": email.split("@")[0]}

    # Firebase Auth token verification (lazy import)
    from backend.app.config import init_firebase

    init_firebase()

    from firebase_admin import auth as firebase_auth

    try:
        decoded = firebase_auth.verify_id_token(token)
        return {
            "uid": decoded["uid"],
            "email": decoded.get("email", ""),
            "display_name": decoded.get("name", "") or "",
        }
    except Exception as err:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from err
