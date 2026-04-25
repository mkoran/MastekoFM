# Sprint E — Multi-user permissions

> Estimated: ~4-5 days
> Branch: `epic/sprint-e-multiuser`
> Goal: Project membership with role-based access; Drive folder sharing; last-admin protection.
> Blocked-by: Sprint B

---

## Why

The system was designed for one user (Marc). With Sprint E it becomes a real multi-user platform.

---

## Definition of Done

- Project has `members: [{uid, email, role, added_at, added_by}]`
- Roles: `owner`, `editor`, `viewer`
- Auth middleware enforces project access
- Adding a member shares the Project's Drive folder with them via Drive API
- Owner can change roles, remove members
- Last-owner protection prevents removing the only owner
- Audit log entry on every membership change
- Tests: each role × each protected operation
- Viewer signing in sees only Projects they're a member of; cannot start a Run

---

## Stories

### E-001 · Project members field (S)

```python
class ProjectMember(BaseModel):
    uid: str
    email: str
    role: Literal["owner", "editor", "viewer"]
    added_at: datetime
    added_by: str  # uid of who added them

class Project:
    ...existing fields...
    members: list[ProjectMember]
```

Migration: existing Projects get `members=[{uid: created_by, role: "owner", ...}]`.

### E-002 · Project access middleware (M)

`middleware/project_access.py`:
```python
def require_project_access(role_required: Literal["viewer", "editor", "owner"]):
    def dep(project_id: str, user: CurrentUser):
        proj = get_project(project_id)
        member = next((m for m in proj.members if m.uid == user["uid"]), None)
        if not member:
            raise HTTPException(403, "Not a project member")
        if not _role_satisfies(member.role, role_required):
            raise HTTPException(403, f"Requires {role_required} role")
        return proj
    return dep
```

Apply to every project-scoped endpoint:
- `GET /api/projects/{id}` → viewer
- `POST /api/projects/{id}/assumption-packs` → editor
- `POST /api/runs` (with project_id) → editor
- `PUT /api/projects/{id}` → owner
- `POST /api/projects/{id}/members` → owner

### E-003 · Last-owner protection (XS)

`POST /api/projects/{id}/members/{uid}/remove`:
```python
remaining_owners = [m for m in proj.members if m.role == "owner" and m.uid != target_uid]
if not remaining_owners:
    raise HTTPException(400, "Cannot remove the last owner")
```

### E-004 · Project Settings UI (M)

`frontend/src/pages/ProjectSettingsPage.tsx`:
- List members with role
- "Invite member" form: email + role
- Per-member: change role dropdown, remove button (disabled for last owner)

### E-005 · Drive folder sharing (S)

When `POST /api/projects/{id}/members` adds a member:
```python
drive_service.share_file(
    file_id=proj.drive_folders.project,  # the project root in Drive
    email=member.email,
    role="writer" if member.role in ("owner", "editor") else "reader",
)
```

Add `share_file` to `services/drive_service.py`:
```python
service.permissions().create(
    fileId=folder_id,
    body={"type": "user", "role": role, "emailAddress": email},
    sendNotificationEmail=True, supportsAllDrives=True,
).execute()
```

### E-006 · UI gating (S)

Hide buttons / disable forms based on role:
- Viewer: read-only everywhere; no "Edit", no "+ New Run", no "Upload"
- Editor: can do runs, edit packs, but no member changes
- Owner: full

UI hiding is convenience; backend is enforcement.

### E-007 · Audit log (S)

Firestore `{prefix}audit_log/{entryId}`:
```python
{
    "project_id": ...,
    "actor_uid": ...,
    "action": "added_member" | "removed_member" | "changed_role",
    "target_uid": ...,
    "details": {...},
    "timestamp": ...,
}
```

Append on every member change. Show in Project Settings UI.

### E-008 · Tests (M)

For each role × each protected endpoint, assert allow/deny matches matrix. Use fake Firebase tokens + multiple test users.

---

## Risks

| Risk | Mitigation |
|---|---|
| Drive sharing fails for Workspace-managed accounts | Test with both consumer + Workspace accounts; surface Drive API errors clearly |
| Member added to Project but Drive share fails | Two-phase: add to Firestore first, then share Drive; if share fails, mark member with `drive_share_pending=true` and retry |
| Role escalation via stale token | Backend always re-checks role on every request |
| Removed member retains Drive access | Removal calls Drive revoke; verify in test |
