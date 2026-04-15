"""Pydantic models for users."""
from datetime import datetime

from pydantic import BaseModel


class UserResponse(BaseModel):
    """User profile returned by the API."""

    uid: str
    email: str
    display_name: str
    created_at: datetime
    updated_at: datetime


class UserInDB(BaseModel):
    """User document as stored in Firestore."""

    uid: str
    email: str
    display_name: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_firestore(cls, doc_dict: dict) -> "UserInDB":
        """Create from Firestore document, tolerating missing fields."""
        return cls(
            uid=doc_dict.get("uid", ""),
            email=doc_dict.get("email", ""),
            display_name=doc_dict.get("display_name", "") or "",
            created_at=doc_dict.get("created_at", datetime.now()),
            updated_at=doc_dict.get("updated_at", datetime.now()),
        )
