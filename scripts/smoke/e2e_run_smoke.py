#!/usr/bin/env python3
"""Sprint INFRA-002: end-to-end smoke test of three-way composition on a live API.

What it does:
  1. POST /api/seed/helloworld  → idempotent; gets back ids for project, model,
                                  pack, output_template
  2. POST /api/runs             → kicks off a Run with those ids
  3. Polls run status until terminal (sync engine returns immediately, but
     this also handles the future async case)
  4. Downloads the output .xlsx from output_download_url
  5. Asserts O_Report!B3==12 (Sum), B4==35 (Product), B5==47 (Total)

Why we need this:
  Pre-Sprint-UX-01, two production bugs (Create Pack 500, Calculate no-op)
  shipped to DEV because the existing smoke (curl /health) couldn't see them.
  This script exercises the actual three-way composition pipeline so the next
  engine/router regression is caught in CI before the deploy completes.

Auth:
  This script needs TWO tokens:
    AUTH_TOKEN          → for the /api endpoints (Bearer header).
                          DEV uses DEV_AUTH_BYPASS, e.g. "dev-ci-smoke@example.com".
                          PROD requires a real Firebase token (so we skip e2e there).
    MFM_DRIVE_TOKEN     → Google Drive access token (drive.file scope), passed
                          via X-MFM-Drive-Token header. Required because seed
                          uploads files to Drive AND run reads the Drive-backed
                          AssumptionPack.

  Sources for MFM_DRIVE_TOKEN (in order):
    1. MFM_DRIVE_TOKEN env var (caller-supplied)
    2. Application Default Credentials with drive.file scope (gcloud auth
       application-default login --scopes=...,https://www.googleapis.com/auth/drive.file)
    3. Workload Identity Federation in CI (the deployer SA needs Drive editor on
       the configured Drive root folder)

  If no token is available and --required is NOT set, the script prints a
  warning and exits 0 (so a local deploy without Drive auth doesn't fail).
  In CI, pass --required so the absence of credentials is a deploy failure.

Usage:
  python scripts/smoke/e2e_run_smoke.py
  API_BASE_URL=https://... AUTH_TOKEN=dev-foo@x MFM_DRIVE_TOKEN=ya29... \\
    python scripts/smoke/e2e_run_smoke.py --required
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from io import BytesIO

# ── Config from env ──────────────────────────────────────────────────────────


def _env_or_die(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        print(f"ERROR: {key} env var is required", file=sys.stderr)
        sys.exit(2)
    return val


# ── Drive token sourcing ─────────────────────────────────────────────────────


def get_drive_token() -> str | None:
    """Return a Drive-scoped access token, or None if none is available."""
    if (token := os.environ.get("MFM_DRIVE_TOKEN")):
        return token
    try:
        import google.auth
        import google.auth.transport.requests
    except ImportError:
        return None
    try:
        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/drive.file"]
        )
        creds.refresh(google.auth.transport.requests.Request())
        return creds.token
    except Exception as exc:
        print(f"  (ADC drive-token mint failed: {exc})", file=sys.stderr)
        return None


# ── HTTP helpers (stdlib only — no extra deps) ───────────────────────────────


def _request(
    method: str,
    url: str,
    *,
    body: dict | None = None,
    auth_token: str = "",
    drive_token: str = "",
    extra_headers: dict | None = None,
) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if auth_token:
        req.add_header("Authorization", f"Bearer {auth_token}")
    if drive_token:
        req.add_header("X-MFM-Drive-Token", drive_token)
    for k, v in (extra_headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = resp.read()
            if not payload:
                return {}
            return json.loads(payload.decode())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        print(f"  HTTP {exc.code} {method} {url}: {body_text}", file=sys.stderr)
        raise


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read()


# ── Main ─────────────────────────────────────────────────────────────────────


def run_e2e(api_base: str, auth_token: str, drive_token: str) -> int:
    """Returns process exit code: 0 success, 1 failure."""
    print(f"E2E smoke against {api_base}")

    # 1. Seed Hello World
    print("  Seeding Hello World…")
    seed = _request(
        "POST", f"{api_base}/api/seed/helloworld",
        body=None, auth_token=auth_token, drive_token=drive_token,
    )
    project_id = seed.get("project_id")
    model_id = seed.get("model_id")
    pack_id = seed.get("assumption_pack_id")
    tpl_id = seed.get("output_template_id")
    if not all([project_id, model_id, pack_id, tpl_id]):
        print(f"  FAIL: seed response missing ids: {seed}", file=sys.stderr)
        return 1
    print(f"    project={project_id} model={model_id} pack={pack_id} tpl={tpl_id}")

    # 2. Create a Run
    print("  Creating Run via three-way composition…")
    run = _request(
        "POST", f"{api_base}/api/runs",
        body={
            "project_id": project_id,
            "model_id": model_id,
            "assumption_pack_id": pack_id,
            "output_template_id": tpl_id,
        },
        auth_token=auth_token, drive_token=drive_token,
    )
    run_id = run.get("id")
    print(f"    run_id={run_id} status={run.get('status')} duration_ms={run.get('duration_ms')}")

    # 3. Poll until terminal (sync engine completes by the time POST returns,
    #    but this code path is ready for Sprint C async)
    deadline = time.time() + 90
    while run.get("status") in ("pending", "running") and time.time() < deadline:
        time.sleep(2)
        run = _request("GET", f"{api_base}/api/runs/{run_id}", auth_token=auth_token)
        print(f"    polling… status={run.get('status')}")

    if run.get("status") != "completed":
        print(f"  FAIL: run did not reach completed (got {run.get('status')!r})", file=sys.stderr)
        if run.get("error"):
            print(f"  Run error: {run['error']}", file=sys.stderr)
        return 1

    # 4. Download output .xlsx
    output_url = run.get("output_download_url")
    if not output_url:
        print("  FAIL: completed run has no output_download_url", file=sys.stderr)
        return 1
    print(f"  Downloading output: {output_url}")
    try:
        output_bytes = _download(output_url)
    except Exception as exc:
        print(f"  FAIL: output download error: {exc}", file=sys.stderr)
        return 1

    # 5. Assert expected cells
    try:
        import openpyxl
    except ImportError:
        print("  WARN: openpyxl not installed — skipping cell assertions", file=sys.stderr)
        print("  ✓ Run completed (cell assertions skipped)")
        return 0

    wb = openpyxl.load_workbook(BytesIO(output_bytes), data_only=True)
    if "O_Report" not in wb.sheetnames:
        print(f"  FAIL: O_Report tab missing. Tabs: {wb.sheetnames}", file=sys.stderr)
        return 1

    ws = wb["O_Report"]
    # Layout (from build_helloworld_seed.py):
    #   B3 = Sum (Model O_Results.sum)         expected 5+7  = 12
    #   B4 = Product (Model O_Results.product) expected 5*7  = 35
    #   B5 = Total (B3 + B4)                   expected      = 47
    actual = {"sum": ws["B3"].value, "product": ws["B4"].value, "total": ws["B5"].value}
    expected = {"sum": 12, "product": 35, "total": 47}

    failures = [
        f"O_Report.{label} expected {expected[label]} got {actual[label]!r}"
        for label in expected if actual[label] != expected[label]
    ]
    if failures:
        for f in failures:
            print(f"  FAIL: {f}", file=sys.stderr)
        return 1

    print(f"  ✓ Hello World cells correct: {actual}")
    print("E2E smoke PASSED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--required", action="store_true",
        help="Fail if no Drive token is available (CI mode)",
    )
    args = parser.parse_args()

    api_base = _env_or_die("API_BASE_URL").rstrip("/")
    auth_token = os.environ.get("AUTH_TOKEN", "")
    if not auth_token:
        print("WARN: AUTH_TOKEN not set — /api endpoints will reject", file=sys.stderr)
        if args.required:
            return 2

    drive_token = get_drive_token()
    if not drive_token:
        msg = "no MFM_DRIVE_TOKEN env var and ADC mint failed"
        if args.required:
            print(f"ERROR: {msg} (--required set)", file=sys.stderr)
            return 2
        print(f"SKIP: {msg} — e2e smoke skipped (deploy not failed)")
        return 0

    return run_e2e(api_base, auth_token, drive_token)


if __name__ == "__main__":
    sys.exit(main())
