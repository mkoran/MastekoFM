"""Auth router — user profile management."""
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.models.user import UserInDB, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def _users_collection() -> str:
    return f"{settings.firestore_collection_prefix}users"


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser):
    """Get current user profile. Creates on first login (upsert)."""
    db = get_firestore_client()
    doc_ref = db.collection(_users_collection()).document(current_user["uid"])
    doc = doc_ref.get()

    if doc.exists:
        user = UserInDB.from_firestore(doc.to_dict())
        updates: dict[str, Any] = {}
        if current_user.get("email") and current_user["email"] != user.email:
            updates["email"] = current_user["email"]
        if current_user.get("display_name") and current_user["display_name"] != user.display_name:
            updates["display_name"] = current_user["display_name"]
        if updates:
            updates["updated_at"] = datetime.now(UTC)
            doc_ref.update(updates)
            user = UserInDB.from_firestore({**doc.to_dict(), **updates})
        return UserResponse(**user.model_dump())

    now = datetime.now(UTC)
    user_data = {
        "uid": current_user["uid"],
        "email": current_user.get("email", ""),
        "display_name": current_user.get("display_name", "") or "",
        "created_at": now,
        "updated_at": now,
    }
    doc_ref.set(user_data)
    return UserResponse(**user_data)
