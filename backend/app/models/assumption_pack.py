"""Pydantic models for Scenarios (per-Excel-Project input files)."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

# ── Sprint I — connector framework ─────────────────────────────────────────────


class PullQuery(BaseModel):
    """A single pull instruction inside a pack's PullSpec.

    A query tells the connector what to fetch and where to put it. The target
    string is either a cell ("I_Numbers.B1") or a whole I_* tab ("I_Numbers"
    — overlays every cell from the source onto the tab).

    The ``config`` is connector-specific (XLSX-Link uses drive_file_id/sheet/
    cell or range; Airtable uses base_id/table/field/aggregate; etc.) and is
    passed verbatim to the connector implementation.
    """

    target: str                                   # "I_Tab.Cell" or "I_Tab"
    kind: Literal["xlsx_link", "airtable"]        # Sprint I-3 will add "qbo"
    config: dict[str, Any]
    fallback: Any = None                          # used when source is None / fails


class PullSpec(BaseModel):
    """Recipe for producing AssumptionPack cell values at Run time.

    Lives on AssumptionPack docs whose pack_kind == "pull". The Run worker
    calls ConnectorRegistry.execute(spec, ...) just before merging the pack's
    I_* values into the Model.
    """

    queries: list[PullQuery]
    on_error: Literal["fail", "warn", "use_fallback"] = "warn"
    cache_ttl_seconds: int = 0   # 0 = always fresh (Sprint I-4 may add caching)


class AssumptionPackCreate(BaseModel):
    """Request body for creating a Scenario.

    Seeds the Scenario file from the Project's Template (I_ tabs only) unless
    clone_from_id is provided, in which case the Scenario file is copied from
    the existing scenario.

    storage_kind overrides the workspace default (see /api/settings) and
    determines whether the file lives in GCS or Drive.

    Sprint I: ``pack_kind`` and ``pull_spec`` introduce non-xlsx pack sources.
    A pull pack has no underlying xlsx — its cell values are produced by
    connectors at Run time.
    """

    name: str
    code_name: str = ""
    description: str = ""
    clone_from_id: str | None = None
    storage_kind: str | None = None  # "gcs" | "drive_xlsx" | None (use default)
    # Sprint I — defaults to xlsx for back-compat
    pack_kind: Literal["xlsx", "json", "pull"] = "xlsx"
    cell_overrides: dict[str, dict[str, Any]] | None = None  # for pack_kind="json"
    pull_spec: PullSpec | None = None                         # for pack_kind="pull"


class AssumptionPackUpdate(BaseModel):
    """Metadata update. File replacement is a separate upload endpoint."""

    name: str | None = None
    code_name: str | None = None
    description: str | None = None
    status: str | None = None
    # Sprint I — switch a pack between source modes / edit its pull-spec
    pack_kind: Literal["xlsx", "json", "pull"] | None = None
    cell_overrides: dict[str, dict[str, Any]] | None = None
    pull_spec: PullSpec | None = None


class AssumptionPackResponse(BaseModel):
    """Full AssumptionPack record."""

    id: str
    name: str
    code_name: str
    description: str
    project_id: str
    pack_number: int = 0              # Sprint G3: per-project counter 1..99 (0 = legacy/unassigned)
    status: str                       # active | archived
    archived: bool = False            # Sprint UX-01: explicit boolean
    pack_kind: Literal["xlsx", "json", "pull"] = "xlsx"  # Sprint I
    cell_overrides: dict[str, dict[str, Any]] | None = None  # Sprint I (json)
    pull_spec: PullSpec | None = None                        # Sprint I (pull)
    storage_kind: str = "drive_xlsx"  # Sprint UX-01: default Drive (post-Sprint-B)
    storage_path: str | None = None   # GCS path when storage_kind=gcs
    drive_folder_id: str | None = None  # Sprint G1: per-pack folder
    drive_folder_url: str | None = None  # Sprint G1: derived URL
    drive_file_id: str | None = None  # latest version's file id
    edit_url: str | None = None       # URL to open in Sheets / download, chosen per store
    size_bytes: int
    version: int                      # increments on every inputs-file replacement
    last_run: dict[str, Any] | None = None  # {run_id, at, status, output_path, ...}
    created_by: str
    created_by_email: str | None = None  # Sprint UX-01
    created_at: datetime
    updated_at: datetime


class AssumptionPackSummary(BaseModel):
    """List-view summary."""

    id: str
    name: str
    code_name: str
    pack_number: int = 0  # Sprint G3
    status: str
    archived: bool = False  # Sprint UX-01
    pack_kind: Literal["xlsx", "json", "pull"] = "xlsx"  # Sprint I — for the source badge
    version: int
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    created_by_email: str | None = None  # Sprint UX-01
    created_at: datetime


class AssumptionPackRunResponse(BaseModel):
    """A single calculation run (legacy /api/projects/{p}/assumption-packs/{s}/runs).

    Sprint A introduced the canonical Run model in models/run.py — this stays
    here only for the legacy assumption_packs router compatibility surface.
    """

    id: str
    scenario_id: str
    project_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    template_version_used: int
    scenario_version_used: int
    input_storage_kind: str | None = None
    input_storage_path: str | None = None
    input_drive_file_id: str | None = None
    input_download_url: str | None = None
    output_storage_path: str | None = None
    output_download_url: str | None = None
    warnings: list[str] = []
    error: str | None = None
