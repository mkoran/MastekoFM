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


class ScenarioStore(Protocol):
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


_STORES: dict[str, ScenarioStore] = {
    STORAGE_KIND_GCS: GCSStore(),
    STORAGE_KIND_DRIVE_XLSX: DriveXlsxStore(),
}


def get_store(kind: str | None) -> ScenarioStore:
    """Return the store adapter for a given kind; defaults to GCS."""
    return _STORES.get(kind or STORAGE_KIND_GCS, _STORES[STORAGE_KIND_GCS])


def store_for_scenario(scn: dict[str, Any]) -> ScenarioStore:
    """Pick the store for a scenario doc. Infers from stored fields as a fallback."""
    kind = scn.get("storage_kind")
    if kind:
        return get_store(kind)
    # Legacy docs without storage_kind: infer from which field is populated.
    if scn.get("drive_file_id"):
        return get_store(STORAGE_KIND_DRIVE_XLSX)
    return get_store(STORAGE_KIND_GCS)
