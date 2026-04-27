"""Scenario storage adapter — abstracts over GCS .xlsx and Drive .xlsx.

Both backends normalize to `.xlsx bytes` at Calculate time, so the engine
(overlay + LibreOffice recalc) is identical regardless of where the Scenario
file lives. What varies is where we read bytes from, where we write them to,
and what editor URL we expose to the UI.

Backends supported today:
  - "gcs"         — file in the masteko-fm-outputs bucket (public URL)
  - "drive_xlsx"  — .xlsx file in a Drive folder, opens in Sheets (Office mode)

"drive_sheet" (native Google Sheets) is a future backend; the adapter
interface is shaped so adding it is additive.
"""
from __future__ import annotations

import logging
from typing import Any, Protocol

from backend.app.services import drive_service, storage_service

logger = logging.getLogger(__name__)

STORAGE_KIND_GCS = "gcs"
STORAGE_KIND_DRIVE_XLSX = "drive_xlsx"

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class AssumptionPackStore(Protocol):
    """Abstract backend for reading/writing Scenario (and Template) files."""

    kind: str

    def read_bytes(self, file_ref: dict[str, Any], *, user_access_token: str | None = None) -> bytes:
        """Read the .xlsx bytes for a file identified by file_ref.

        file_ref is the scenario (or template) Firestore dict. It must contain
        enough info to locate the artifact for THIS store.
        """
        ...

    def write_bytes(
        self,
        *,
        project_code: str,
        scenario_code: str,
        kind_label: str,
        version: int,
        filename: str,
        content: bytes,
        existing: dict[str, Any] | None = None,
        user_access_token: str | None = None,
    ) -> dict[str, Any]:
        """Write .xlsx bytes for a new Scenario or a replacement version.

        Returns a dict of Firestore fields to merge into the scenario doc.
        kind_label is "inputs" for scenario inputs or "outputs" for outputs.
        """
        ...

    def open_url(self, file_ref: dict[str, Any]) -> str | None:
        """URL to open the file in a human-editable tool, or None if not applicable."""
        ...


# ─── GCS backend ─────────────────────────────────────────────────────────────


class GCSStore:
    kind = STORAGE_KIND_GCS

    def read_bytes(self, file_ref: dict[str, Any], *, user_access_token: str | None = None) -> bytes:
        path = file_ref.get("storage_path") or ""
        if not path:
            raise ValueError("GCS scenario has no storage_path")
        return storage_service.download_xlsx(path)

    def write_bytes(
        self,
        *,
        project_code: str,
        scenario_code: str,
        kind_label: str,
        version: int,
        filename: str,
        content: bytes,
        existing: dict[str, Any] | None = None,
        user_access_token: str | None = None,
    ) -> dict[str, Any]:
        sub = "inputs" if kind_label == "inputs" else "outputs"
        if kind_label == "inputs":
            path = f"excel_projects/{project_code}/{scenario_code}/{sub}_v{version}.xlsx"
        else:
            path = f"excel_projects/{project_code}/{scenario_code}/{sub}/{filename}"
        storage_service.upload_xlsx(path, content, download_filename=filename)
        return {
            "storage_kind": self.kind,
            "storage_path": path,
            "drive_file_id": None,
            "size_bytes": len(content),
        }

    def open_url(self, file_ref: dict[str, Any]) -> str | None:
        path = file_ref.get("storage_path") or ""
        if not path:
            return None
        return storage_service.public_url(path)


# ─── Drive XLSX backend ──────────────────────────────────────────────────────


class DriveXlsxStore:
    """Stores .xlsx in Drive. Editor URL opens in Sheets in Office mode.

    Structure used in Drive:
      <drive_root>/MastekoFM/<project_code>/Inputs/<scenario>.xlsx
      <drive_root>/MastekoFM/<project_code>/Outputs/<timestamp>_<project>_<scenario>.xlsx

    We rely on a per-project folder id cached on the project doc
    (drive_project_folder_id) or create-and-cache lazily.
    """

    kind = STORAGE_KIND_DRIVE_XLSX

    def read_bytes(self, file_ref: dict[str, Any], *, user_access_token: str | None = None) -> bytes:
        file_id = file_ref.get("drive_file_id")
        if not file_id:
            raise ValueError("Drive scenario has no drive_file_id")
        content = drive_service.download_file(file_id, user_access_token=user_access_token)
        if content is None:
            raise RuntimeError(f"Drive download failed for file_id={file_id}")
        return content

    def write_bytes(
        self,
        *,
        project_code: str,
        scenario_code: str,
        kind_label: str,
        version: int,
        filename: str,
        content: bytes,
        existing: dict[str, Any] | None = None,
        user_access_token: str | None = None,
    ) -> dict[str, Any]:
        """Write to Drive. Requires:
          existing['drive_folder_id']  (the Inputs/ or Outputs/ folder for this project)
        OR ValueError if not preresolved.

        For a replacement version of an existing Drive file, if
        existing['drive_file_id'] is set AND kind_label == "inputs",
        we overwrite that same file (preserves the Sheets editor URL).
        """
        if not existing:
            existing = {}
        folder_id = existing.get("drive_folder_id")
        if not folder_id:
            raise ValueError(
                "DriveXlsxStore.write_bytes requires existing['drive_folder_id']; "
                "call drive_service.ensure_project_folders() first."
            )

        # Overwrite in place when we already have a Drive file id and are writing inputs.
        existing_file_id = existing.get("drive_file_id") if kind_label == "inputs" else None
        if existing_file_id:
            drive_service.update_file_content(
                existing_file_id, content, mime_type=XLSX_MIME,
                user_access_token=user_access_token,
            )
            file_id = existing_file_id
        else:
            file_id = drive_service.upload_file(
                folder_id, filename, content, XLSX_MIME,
                user_access_token=user_access_token,
            )
            if file_id is None:
                raise RuntimeError("Drive upload returned no id")

        return {
            "storage_kind": self.kind,
            "storage_path": None,
            "drive_file_id": file_id,
            "size_bytes": len(content),
        }

    def open_url(self, file_ref: dict[str, Any]) -> str | None:
        file_id = file_ref.get("drive_file_id")
        if not file_id:
            return None
        # Opens in Sheets automatically — in Office mode for .xlsx files.
        return f"https://docs.google.com/spreadsheets/d/{file_id}/edit"


# ─── Factory ──────────────────────────────────────────────────────────────────


_STORES: dict[str, AssumptionPackStore] = {
    STORAGE_KIND_GCS: GCSStore(),
    STORAGE_KIND_DRIVE_XLSX: DriveXlsxStore(),
}


def get_store(kind: str | None) -> AssumptionPackStore:
    """Return the store adapter for a given kind; defaults to GCS."""
    return _STORES.get(kind or STORAGE_KIND_GCS, _STORES[STORAGE_KIND_GCS])


def store_for_scenario(scn: dict[str, Any]) -> AssumptionPackStore:
    """Pick the store for a scenario doc. Infers from stored fields as a fallback."""
    kind = scn.get("storage_kind")
    if kind:
        return get_store(kind)
    # Legacy docs without storage_kind: infer from which field is populated.
    if scn.get("drive_file_id"):
        return get_store(STORAGE_KIND_DRIVE_XLSX)
    return get_store(STORAGE_KIND_GCS)


# ── High-level loaders (Sprint B) ────────────────────────────────────────────
# These centralize "given a Firestore doc for X, return its xlsx bytes". Used by
# the runs router so route handlers don't have to know about storage internals.
#
# Sprint F.1 — Drive-token fallback:
#   The narrow `drive.file` OAuth scope only sees files the SAME Google account
#   uploaded via this app. If a user signs in with a DIFFERENT Google account
#   than the one that uploaded the file, the user's token returns 404. Fix:
#   try the user's token first; on failure, mint an SA-scoped token (which has
#   broader `drive` scope and can see anything in the shared MastekoFM folder)
#   and retry. Falls back transparently — happy path is unchanged.


def _try_sa_drive_token() -> str | None:
    """Mint a Drive-scoped access token from the runtime SA, or None if unavailable.

    The deployer / runtime SA has Editor access to the MastekoFM Drive root
    (granted at project creation). Its `drive` scope sees everything inside,
    independent of which user account uploaded which file.
    """
    try:
        import google.auth
        import google.auth.transport.requests
    except ImportError:
        return None
    try:
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/drive"])
        creds.refresh(google.auth.transport.requests.Request())
        return creds.token
    except Exception as exc:  # noqa: BLE001
        logger.info("SA drive-token mint failed (%s); user token only", exc)
        return None


def _download_with_fallback(file_id: str, user_token: str | None, label: str) -> bytes:
    """Try user_token first, then fall back to SA-minted drive-scope token."""
    # Try 1: user's token (drive.file scope — narrow but happy path)
    if user_token:
        content = drive_service.download_file(file_id, user_access_token=user_token)
        if content is not None:
            return content
        logger.info(
            "Drive download via user token failed for %s file_id=%s — trying SA fallback",
            label, file_id,
        )
    # Try 2: SA token (drive scope — broad, but only sees files in the shared folder)
    sa_token = _try_sa_drive_token()
    if sa_token:
        content = drive_service.download_file(file_id, user_access_token=sa_token)
        if content is not None:
            return content
    raise RuntimeError(
        f"Drive download failed for {label} file_id={file_id} "
        f"(tried both user token and SA-fallback). "
        f"Likely cause: the file is owned by a Google account NOT signed into this app, "
        f"AND not shared with the deployer service account. Either sign in with the "
        f"owning account, or share the MastekoFM Drive folder with the runtime SA."
    )


def load_model_bytes_compat(model: dict[str, Any], *, user_token: str | None = None) -> bytes:
    """Load a Model's xlsx bytes (Drive or GCS depending on what it has).

    Sprint F.1: now accepts user_token for Drive-backed Models (was missing).
    """
    if model.get("drive_file_id"):
        return _download_with_fallback(model["drive_file_id"], user_token, "model")
    if model.get("storage_path"):
        return storage_service.download_xlsx(model["storage_path"])
    raise ValueError("Model has neither drive_file_id nor storage_path")


def load_pack_bytes_compat(pack: dict[str, Any], *, user_token: str | None = None) -> bytes:
    """Load an AssumptionPack's xlsx bytes."""
    if pack.get("storage_kind") == STORAGE_KIND_DRIVE_XLSX or pack.get("drive_file_id"):
        if not pack.get("drive_file_id"):
            raise ValueError("Drive-backed pack has no drive_file_id")
        return _download_with_fallback(pack["drive_file_id"], user_token, "pack")
    if pack.get("storage_path"):
        return storage_service.download_xlsx(pack["storage_path"])
    raise ValueError("AssumptionPack has neither drive_file_id nor storage_path")


def load_output_template_bytes_compat(tpl: dict[str, Any], *, user_token: str | None = None) -> bytes:
    """Load an OutputTemplate's xlsx bytes (Drive-only by design)."""
    if not tpl.get("drive_file_id"):
        raise ValueError("OutputTemplate must be Drive-backed")
    return _download_with_fallback(tpl["drive_file_id"], user_token, "output_template")
