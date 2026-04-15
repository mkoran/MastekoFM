"""Projects router — CRUD for projects."""
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.models.project import ProjectCreate, ProjectInDB, ProjectResponse, ProjectUpdate
from backend.app.services.drive_service import create_project_folder

router = APIRouter(prefix="/api/projects", tags=["projects"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def _projects_collection() -> str:
    return f"{settings.firestore_collection_prefix}projects"


def _project_to_response(doc_id: str, data: dict[str, Any]) -> ProjectResponse:
    project = ProjectInDB.from_firestore(data)
    return ProjectResponse(id=doc_id, **project.model_dump(exclude={"drive_folder_id"}))


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(body: ProjectCreate, current_user: CurrentUser):
    """Create a new project."""
    now = datetime.now(UTC)
    project_data = {
        "name": body.name,
        "owner_uid": current_user["uid"],
        "status": "active",
        "checkout": {},
        "created_at": now,
        "updated_at": now,
    }

    # Create Drive folder (best-effort — don't fail project creation)
    folder_id = create_project_folder(body.name)
    if folder_id:
        project_data["drive_folder_id"] = folder_id

    doc_ref = get_firestore_client().collection(_projects_collection()).document()
    doc_ref.set(project_data)
    return _project_to_response(doc_ref.id, project_data)


@router.get("", response_model=list[ProjectResponse])
async def list_projects(current_user: CurrentUser):
    """List projects owned by the current user."""
    docs = (
        get_firestore_client().collection(_projects_collection())
        .where("owner_uid", "==", current_user["uid"])
        .where("status", "==", "active")
        .stream()
    )
    return [_project_to_response(doc.id, doc.to_dict()) for doc in docs]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, current_user: CurrentUser):
    """Get a single project."""
    doc = get_firestore_client().collection(_projects_collection()).document(project_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Project not found")
    data = doc.to_dict()
    if data.get("owner_uid") != current_user["uid"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return _project_to_response(doc.id, data)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, body: ProjectUpdate, current_user: CurrentUser):
    """Update a project."""
    doc_ref = get_firestore_client().collection(_projects_collection()).document(project_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Project not found")
    data = doc.to_dict()
    if data.get("owner_uid") != current_user["uid"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    updates: dict[str, Any] = {"updated_at": datetime.now(UTC)}
    if body.name is not None:
        updates["name"] = body.name
    doc_ref.update(updates)
    return _project_to_response(project_id, {**data, **updates})


@router.post("/{project_id}/archive", response_model=ProjectResponse)
async def archive_project(project_id: str, current_user: CurrentUser):
    """Archive a project (soft delete)."""
    doc_ref = get_firestore_client().collection(_projects_collection()).document(project_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Project not found")
    data = doc.to_dict()
    if data.get("owner_uid") != current_user["uid"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    updates = {"status": "archived", "updated_at": datetime.now(UTC)}
    doc_ref.update(updates)
    return _project_to_response(project_id, {**data, **updates})


@router.post("/{project_id}/create-drive-folder")
async def create_drive_folder_for_project(project_id: str, current_user: CurrentUser):
    """Create a Google Drive folder for a project that doesn't have one yet."""
    doc_ref = get_firestore_client().collection(_projects_collection()).document(project_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Project not found")
    data = doc.to_dict()
    if data.get("drive_folder_id"):
        return {"message": "Drive folder already exists", "drive_folder_id": data["drive_folder_id"]}

    folder_id = create_project_folder(data.get("name", "Untitled"))
    if folder_id:
        doc_ref.update({"drive_folder_id": folder_id, "updated_at": datetime.now(UTC)})
        return {"message": "Drive folder created", "drive_folder_id": folder_id}
    raise HTTPException(status_code=500, detail="Failed to create Drive folder. Check DRIVE_ROOT_FOLDER_ID.")


# ─── Checkout endpoints ───

CHECKOUT_DURATION_HOURS = 2


def _is_checkout_active(checkout: dict[str, Any]) -> bool:
    """Check if a checkout is still active (not expired)."""
    if not checkout.get("user_uid"):
        return False
    expires_at = checkout.get("expires_at")
    if expires_at is None:
        return False
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    return expires_at > datetime.now(UTC)


@router.post("/{project_id}/checkout", response_model=ProjectResponse)
async def checkout_project(project_id: str, current_user: CurrentUser):
    """Acquire a checkout lock on a project (2-hour expiry)."""
    doc_ref = get_firestore_client().collection(_projects_collection()).document(project_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Project not found")
    data = doc.to_dict()

    checkout = data.get("checkout", {}) or {}
    if _is_checkout_active(checkout) and checkout.get("user_uid") != current_user["uid"]:
        raise HTTPException(
            status_code=409,
            detail=f"Project checked out by {checkout.get('user_name', 'another user')}",
        )

    now = datetime.now(UTC)
    new_checkout = {
        "user_uid": current_user["uid"],
        "user_name": current_user.get("display_name", current_user.get("email", "")),
        "checked_out_at": now,
        "expires_at": now + timedelta(hours=CHECKOUT_DURATION_HOURS),
    }
    doc_ref.update({"checkout": new_checkout, "updated_at": now})
    return _project_to_response(project_id, {**data, "checkout": new_checkout, "updated_at": now})


@router.post("/{project_id}/checkin", response_model=ProjectResponse)
async def checkin_project(project_id: str, current_user: CurrentUser):
    """Release a checkout lock."""
    doc_ref = get_firestore_client().collection(_projects_collection()).document(project_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Project not found")
    data = doc.to_dict()

    checkout = data.get("checkout", {}) or {}
    holder = checkout.get("user_uid")
    if holder and holder != current_user["uid"] and data.get("owner_uid") != current_user["uid"]:
        raise HTTPException(status_code=403, detail="Only the holder or owner can release the checkout")

    empty_checkout: dict[str, Any] = {"user_uid": None, "user_name": None, "checked_out_at": None, "expires_at": None}
    now = datetime.now(UTC)
    doc_ref.update({"checkout": empty_checkout, "updated_at": now})
    return _project_to_response(project_id, {**data, "checkout": empty_checkout, "updated_at": now})


@router.post("/{project_id}/force-release", response_model=ProjectResponse)
async def force_release(project_id: str, current_user: CurrentUser):
    """Force-release a checkout. Owner only."""
    doc_ref = get_firestore_client().collection(_projects_collection()).document(project_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Project not found")
    data = doc.to_dict()
    if data.get("owner_uid") != current_user["uid"]:
        raise HTTPException(status_code=403, detail="Only the project owner can force-release")

    empty_checkout: dict[str, Any] = {"user_uid": None, "user_name": None, "checked_out_at": None, "expires_at": None}
    now = datetime.now(UTC)
    doc_ref.update({"checkout": empty_checkout, "updated_at": now})
    return _project_to_response(project_id, {**data, "checkout": empty_checkout, "updated_at": now})
