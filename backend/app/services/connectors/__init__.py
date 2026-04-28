"""Sprint I — connector framework.

A connector is anything that can produce ``CellOverrides`` from a
``PullQuery``. The Run worker invokes connectors at execution time so a
pack's values reflect the source-of-truth system NOW (live data), not
whenever Marc last typed them into a spreadsheet.

Public surface:

    from backend.app.services.connectors import execute_pull_spec

    overrides = execute_pull_spec(spec, ctx)
    # → {"I_Numbers": {"B1": 5, "B2": 7}, "I_Pricing": {"B5": 1500, ...}}

Each connector implementation registers itself by importing into this
package. See xlsx_link.py for the canonical implementation.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from backend.app.models.assumption_pack import PullQuery, PullSpec

logger = logging.getLogger(__name__)


class ConnectorContext:
    """Per-execution context passed to every connector.

    Carries auth tokens, workspace + run identifiers, and access to other
    Workspace-scoped resources (e.g. Airtable connection records).
    """

    def __init__(
        self,
        *,
        user_drive_token: str | None = None,
        workspace_id: str | None = None,
        run_id: str | None = None,
    ) -> None:
        self.user_drive_token = user_drive_token
        self.workspace_id = workspace_id
        self.run_id = run_id


class ConnectorResult:
    """One connector invocation's output.

    cell_writes: nested {tab_name: {cell_ref: value, ...}, ...}
    warnings:    list of human-readable strings (logged + surfaced on Run doc)
    provenance:  list of {target, source_kind, source_ref, fetched_at_iso}
    """

    def __init__(self) -> None:
        self.cell_writes: dict[str, dict[str, Any]] = {}
        self.warnings: list[str] = []
        self.provenance: list[dict[str, Any]] = []

    def write_cell(self, tab: str, cell_ref: str, value: Any) -> None:
        self.cell_writes.setdefault(tab, {})[cell_ref] = value


# ConnectorFn(query, ctx, result) — mutates result in place.
ConnectorFn = Callable[[PullQuery, ConnectorContext, ConnectorResult], None]
_REGISTRY: dict[str, ConnectorFn] = {}


def register(kind: str, fn: ConnectorFn) -> None:
    """Register a connector implementation. Called once at import time."""
    if kind in _REGISTRY:
        logger.warning("Connector %r being re-registered (overwriting)", kind)
    _REGISTRY[kind] = fn


def get_connector(kind: str) -> ConnectorFn:
    """Look up a connector by kind. Raises KeyError if unregistered."""
    if kind not in _REGISTRY:
        raise KeyError(f"No connector registered for kind={kind!r}")
    return _REGISTRY[kind]


def parse_target(target: str) -> tuple[str, str | None]:
    """Split a query target into (tab, cell_or_None).

    "I_Numbers.B1" → ("I_Numbers", "B1")     — single-cell write
    "I_Numbers"    → ("I_Numbers", None)     — whole-tab overlay
    """
    if "." in target:
        tab, cell = target.split(".", 1)
        return tab, cell
    return target, None


def execute_pull_spec(
    spec: PullSpec, ctx: ConnectorContext,
) -> ConnectorResult:
    """Run every query in ``spec`` and return a merged ConnectorResult.

    Honors ``spec.on_error``:
      - "fail":          first failed query raises
      - "warn":          failures recorded as warnings; fallback used if set
      - "use_fallback":  same as "warn" but silent (no warning recorded)
    """
    result = ConnectorResult()
    for q in spec.queries:
        try:
            fn = get_connector(q.kind)
        except KeyError as exc:
            msg = f"unknown connector kind {q.kind!r}: {exc}"
            if spec.on_error == "fail":
                raise
            if spec.on_error == "warn":
                result.warnings.append(msg)
            _apply_fallback(q, result)
            continue

        try:
            fn(q, ctx, result)
        except Exception as exc:  # noqa: BLE001 — connectors guard their own
            msg = f"connector {q.kind!r} failed on target={q.target!r}: {exc}"
            logger.warning(msg, exc_info=True)
            if spec.on_error == "fail":
                raise
            if spec.on_error == "warn":
                result.warnings.append(msg)
            _apply_fallback(q, result)
    return result


def _apply_fallback(q: PullQuery, result: ConnectorResult) -> None:
    """If the query has a fallback value, write it at the target."""
    if q.fallback is None:
        return
    tab, cell = parse_target(q.target)
    if cell is None:
        # Tab-level fallback isn't supported (no shape known); skip.
        return
    result.write_cell(tab, cell, q.fallback)


# Auto-register all connector implementations at import time.
from backend.app.services.connectors import airtable as _airtable  # noqa: E402,F401
from backend.app.services.connectors import xlsx_link as _xlsx_link  # noqa: E402,F401
