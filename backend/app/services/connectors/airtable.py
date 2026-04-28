"""Sprint I-2 — Airtable connector.

Reads cells from an Airtable base via the REST API. Auth is a Personal
Access Token (PAT) or legacy API key, stored under a workspace's
``connections`` subcollection (KMS-encrypted at rest).

Three query shapes:

    Cell mode:   target="I_Numbers.B1"
                 config={"connection_id":"...", "base_id":"appXXXX",
                         "table":"Properties",
                         "filter":"{Name}='Campus Adele'",
                         "field":"Square Feet"}
                 → first matching record's field value

    Aggregate:   target="I_Total.B1"
                 config={"connection_id":"...", "base_id":"appXXXX",
                         "table":"Properties",
                         "filter":"{Status}='Active'",
                         "field":"Annual Rent",
                         "aggregate":"sum"}                # sum|mean|count|min|max
                 → over all matching records

    Tab mode:    target="I_Properties"
                 config={"connection_id":"...", "base_id":"appXXXX",
                         "table":"Properties",
                         "filter":"{Status}='Active'",
                         "fields":["Name","Sq Ft","Annual Rent"]}
                 → records overlay onto the I_* tab as a 2-D grid:
                     Row 1: header (field names)
                     Row 2..N: each record's values

Security: the PAT is fetched from KMS-encrypted storage just-in-time per
query and never logged.
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
import urllib.parse
import urllib.request
from typing import Any

from backend.app.config import get_firestore_client, settings
from backend.app.models.assumption_pack import PullQuery
from backend.app.services import secrets as secrets_svc
from backend.app.services.connectors import parse_target, register

logger = logging.getLogger(__name__)

AIRTABLE_API_BASE = "https://api.airtable.com/v0"
COL_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _now_iso() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat()


def _col_letter(idx: int) -> str:
    """0 → A, 1 → B, ..., 25 → Z, 26 → AA, etc."""
    if idx < 0:
        raise ValueError("col index < 0")
    out = ""
    n = idx
    while True:
        out = COL_LETTERS[n % 26] + out
        n = n // 26 - 1
        if n < 0:
            break
    return out


def _load_connection(workspace_id: str | None, connection_id: str) -> dict[str, Any]:
    """Read a workspace connection doc + decrypt its secret."""
    if not workspace_id:
        raise RuntimeError("Airtable connector requires workspace_id in context")
    db = get_firestore_client()
    prefix = settings.firestore_collection_prefix
    doc = (
        db.collection(f"{prefix}workspaces")
        .document(workspace_id)
        .collection("connections")
        .document(connection_id)
        .get()
    )
    if not doc.exists:
        raise RuntimeError(
            f"Connection {connection_id} not found under workspace {workspace_id}"
        )
    data = doc.to_dict() or {}
    if data.get("kind") != "airtable":
        raise RuntimeError(
            f"Connection {connection_id} is kind={data.get('kind')!r}, expected 'airtable'"
        )
    enc = data.get("secret_encrypted")
    if not enc:
        raise RuntimeError(f"Connection {connection_id} has no encrypted secret")
    secret = secrets_svc.decrypt(enc)
    return {**data, "secret": secret}


def _airtable_list_records(
    *, base_id: str, table: str, secret: str, filter_formula: str | None = None,
    fields: list[str] | None = None, max_records: int = 1000,
) -> list[dict[str, Any]]:
    """Fetch all records (paged) for a table + filter. Returns list of
    Airtable record dicts ({id, fields, ...})."""
    out: list[dict[str, Any]] = []
    offset: str | None = None
    safe_table = urllib.parse.quote(table, safe="")
    while True:
        params: dict[str, Any] = {"pageSize": min(100, max_records - len(out))}
        if filter_formula:
            params["filterByFormula"] = filter_formula
        if fields:
            params["fields[]"] = fields
        if offset:
            params["offset"] = offset
        # Airtable expects fields[]=X&fields[]=Y — urlencode with doseq handles it.
        qs = urllib.parse.urlencode(params, doseq=True)
        url = f"{AIRTABLE_API_BASE}/{base_id}/{safe_table}?{qs}"
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {secret}"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
        records = payload.get("records", [])
        out.extend(records)
        offset = payload.get("offset")
        if not offset or len(out) >= max_records:
            break
    return out[:max_records]


def _aggregate(values: list[Any], op: str) -> Any:
    nums = [v for v in values if isinstance(v, int | float) and not isinstance(v, bool)]
    if op == "count":
        return len([v for v in values if v is not None])
    if not nums:
        return None
    if op == "sum":
        return sum(nums)
    if op == "mean":
        return sum(nums) / len(nums)
    if op == "min":
        return min(nums)
    if op == "max":
        return max(nums)
    raise ValueError(f"Unknown aggregate op: {op!r}")


def execute(query: PullQuery, ctx, result) -> None:
    cfg = query.config or {}
    connection_id: str = cfg["connection_id"]
    base_id: str = cfg.get("base_id") or ""
    table: str = cfg["table"]
    filter_formula: str | None = cfg.get("filter")

    conn = _load_connection(ctx.workspace_id, connection_id)
    secret = conn["secret"]
    # Fall back to base_id stored on the connection itself (Marc may bind a
    # connection to a single base for convenience).
    base_id = base_id or conn.get("metadata", {}).get("base_id", "")
    if not base_id:
        raise RuntimeError("airtable: base_id required (in config or connection metadata)")

    target_tab, target_cell = parse_target(query.target)

    # ── Tab mode ────────────────────────────────────────────────────────────
    if target_cell is None:
        fields: list[str] = cfg.get("fields") or []
        records = _airtable_list_records(
            base_id=base_id, table=table, secret=secret,
            filter_formula=filter_formula, fields=fields or None,
        )
        # Determine the column order. Explicit `fields` wins; else discover
        # from the first record.
        if not fields and records:
            fields = list(records[0].get("fields", {}).keys())
        # Header row
        for i, fname in enumerate(fields):
            result.write_cell(target_tab, f"{_col_letter(i)}1", fname)
        # Data rows
        for r_idx, rec in enumerate(records, start=2):
            rec_fields = rec.get("fields", {})
            for c_idx, fname in enumerate(fields):
                value = rec_fields.get(fname)
                if value is not None:
                    result.write_cell(target_tab, f"{_col_letter(c_idx)}{r_idx}", value)
        result.provenance.append({
            "target": query.target,
            "source_kind": "airtable",
            "source_ref": f"{base_id}/{table} (records={len(records)}, fields={len(fields)})",
            "fetched_at": _now_iso(),
            "records": len(records),
        })
        logger.info(
            "airtable tab overlay: %s/%s → %s (%d records, %d fields)",
            base_id, table, target_tab, len(records), len(fields),
        )
        return

    # ── Cell or Aggregate mode ──────────────────────────────────────────────
    field_name: str = cfg["field"]
    aggregate_op: str | None = cfg.get("aggregate")
    records = _airtable_list_records(
        base_id=base_id, table=table, secret=secret,
        filter_formula=filter_formula, fields=[field_name],
    )
    values = [r.get("fields", {}).get(field_name) for r in records]

    if aggregate_op:
        value: Any = _aggregate(values, aggregate_op)
        source_ref = f"{base_id}/{table} ({aggregate_op} of {field_name})"
    else:
        value = values[0] if values else None
        source_ref = f"{base_id}/{table}.{field_name}"

    if value is None and query.fallback is not None:
        value = query.fallback
        result.warnings.append(
            f"airtable {source_ref} returned None; using fallback {query.fallback!r}"
        )
    result.write_cell(target_tab, target_cell, value)
    result.provenance.append({
        "target": query.target,
        "source_kind": "airtable",
        "source_ref": source_ref,
        "fetched_at": _now_iso(),
        "value": value,
    })
    logger.info("airtable cell: %s = %r", source_ref, value)


register("airtable", execute)
