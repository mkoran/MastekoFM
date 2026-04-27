#!/usr/bin/env python3
"""Sprint G1 — wipe + re-seed DEV under the new Workspace + versioned-filename layout.

What it does:
  1. Confirms env=dev (refuses to run against prod_)
  2. Lists current dev_workspaces, dev_models, dev_output_templates,
     dev_projects (+ subcollections), dev_runs
  3. Asks for explicit confirmation
  4. Deletes all Firestore docs under dev_*
  5. Calls /api/seed/helloworld against the live DEV API (you provide a
     Drive-scoped access token — easiest source: paste from your browser
     devtools after signing in, OR mint via gcloud impersonating the
     deployer SA with --scopes=drive)

Drive folders in your account are NOT touched (orphaned folders / files
remain — clean up manually in Drive UI if you care). Firestore docs are
the source of truth; orphan Drive folders are just clutter.

Usage:
  python scripts/migrate/wipe_and_reseed_dev.py             # dry run — lists what would be deleted
  python scripts/migrate/wipe_and_reseed_dev.py --confirm   # actually wipes + re-seeds

Env:
  MFM_DRIVE_TOKEN  Drive access token (drive scope). If unset, script tries to
                   mint one via gcloud impersonating mfm-deployer.
  MFM_API_BASE     Override the API URL. Defaults to the live DEV Cloud Run URL.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

DEFAULT_API = "https://masteko-fm-api-dev-snfqtbi55a-nn.a.run.app"
PROJECT = "masteko-fm"
PREFIX = "dev_"

COLLECTIONS = [
    "dev_workspaces",
    "dev_models",
    "dev_output_templates",
    "dev_runs",
    # dev_projects has nested subcollections:
    "dev_projects",
]
# Subcollections to walk under each project doc
PROJECT_SUBCOLLECTIONS = ["assumption_packs"]


def _gcloud_token() -> str:
    """Mint a cloud-platform token for Firestore REST calls."""
    out = subprocess.run(
        ["gcloud", "auth", "print-access-token"], capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def _drive_token_via_sa() -> str | None:
    """Mint a drive-scope token via SA impersonation (Marc's user has TokenCreator)."""
    try:
        out = subprocess.run(
            [
                "gcloud", "auth", "print-access-token",
                "--impersonate-service-account=mfm-deployer@masteko-fm.iam.gserviceaccount.com",
                "--scopes=https://www.googleapis.com/auth/drive",
            ],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except subprocess.CalledProcessError as exc:
        print(f"  (SA token mint failed: {exc.stderr.strip().splitlines()[-1] if exc.stderr else exc})", file=sys.stderr)
        return None


def _firestore_get(path: str, token: str) -> dict:
    url = f"https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents/{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}
        raise


def _firestore_list(collection: str, token: str) -> list[dict]:
    """Walk a collection (page through all docs)."""
    out: list[dict] = []
    page_token = None
    while True:
        url = (
            f"https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)"
            f"/documents/{collection}?pageSize=300"
        )
        if page_token:
            url += f"&pageToken={page_token}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req) as r:
                resp = json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return out
            raise
        out.extend(resp.get("documents", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return out


def _firestore_delete(doc_name: str, token: str) -> bool:
    """Delete a Firestore document by full resource name. Returns True if deleted."""
    url = f"https://firestore.googleapis.com/v1/{doc_name}"
    req = urllib.request.Request(url, method="DELETE", headers={"Authorization": f"Bearer {token}"})
    try:
        urllib.request.urlopen(req)
        return True
    except urllib.error.HTTPError as e:
        print(f"  (delete failed for {doc_name}: HTTP {e.code})", file=sys.stderr)
        return False


def collect_targets(token: str) -> dict[str, list[str]]:
    """Returns {collection_name: [doc_resource_name, ...]}."""
    targets: dict[str, list[str]] = {}
    for coll in COLLECTIONS:
        docs = _firestore_list(coll, token)
        targets[coll] = [d["name"] for d in docs]
        # For projects, also walk each project's subcollections
        if coll == "dev_projects":
            for d in docs:
                proj_path = d["name"].split("/documents/", 1)[1]
                for sub in PROJECT_SUBCOLLECTIONS:
                    sub_path = f"{proj_path}/{sub}"
                    sub_docs = _firestore_list(sub_path, token)
                    if sub_docs:
                        targets.setdefault(sub_path, []).extend(d2["name"] for d2 in sub_docs)
    return targets


def wipe(targets: dict[str, list[str]], token: str) -> int:
    """Delete all targets. Returns count deleted."""
    count = 0
    # Delete subcollections first so parent deletes don't orphan
    keys = sorted(targets.keys(), key=lambda k: -k.count("/"))
    for k in keys:
        for doc_name in targets[k]:
            if _firestore_delete(doc_name, token):
                count += 1
                print(f"  ✓ deleted {doc_name.split('/')[-1]} ({k})")
    return count


def reseed(api_base: str, drive_token: str) -> dict:
    """POST /api/seed/helloworld and return the response."""
    url = f"{api_base.rstrip('/')}/api/seed/helloworld"
    req = urllib.request.Request(url, data=b"", method="POST")
    req.add_header("Authorization", "Bearer dev-cli-migrate@example.com")
    req.add_header("X-MFM-Drive-Token", drive_token)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", action="store_true",
                        help="Actually delete + re-seed (default is dry-run)")
    parser.add_argument("--api-base", default=os.environ.get("MFM_API_BASE", DEFAULT_API))
    parser.add_argument("--skip-reseed", action="store_true",
                        help="Wipe only; don't call /api/seed/helloworld after")
    args = parser.parse_args()

    token = _gcloud_token()
    print("── Sprint G1 wipe + re-seed (DEV) ─────────────────────────────")

    targets = collect_targets(token)
    total = sum(len(v) for v in targets.values())
    print(f"\nCurrent DEV Firestore state:")
    for k, names in sorted(targets.items()):
        print(f"  {k}: {len(names)} doc(s)")
    print(f"\nTotal docs to delete: {total}")

    if not args.confirm:
        print("\n[dry-run] No changes made. Re-run with --confirm to actually wipe.")
        return 0

    print("\n⚠ DELETING all DEV Firestore docs in 5 seconds (Ctrl+C to abort)...")
    import time
    time.sleep(5)
    deleted = wipe(targets, token)
    print(f"\n✓ Deleted {deleted} doc(s)")

    if args.skip_reseed:
        return 0

    print("\nMinting Drive token + calling /api/seed/helloworld...")
    drive_token = os.environ.get("MFM_DRIVE_TOKEN") or _drive_token_via_sa()
    if not drive_token:
        print("\n⚠ No Drive token available. Set MFM_DRIVE_TOKEN or grant TokenCreator on mfm-deployer.")
        print("  Skipping re-seed. Sign in to dev-masteko-fm.web.app to trigger workspace + seed manually.")
        return 0

    try:
        result = reseed(args.api_base, drive_token)
        print("\n✓ Re-seeded Hello World:")
        print(f"  workspace_id : {result.get('workspace_id')}")
        print(f"  workspace_code: {result.get('workspace_code')}")
        print(f"  project_id   : {result.get('project_id')}")
        print(f"  model_id     : {result.get('model_id')}")
        print(f"  pack_id      : {result.get('assumption_pack_id')}")
        print(f"  template_id  : {result.get('output_template_id')}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"\n⚠ Seed failed: HTTP {e.code} {body[:500]}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
