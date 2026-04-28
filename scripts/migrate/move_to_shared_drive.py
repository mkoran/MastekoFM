#!/usr/bin/env python3
"""Sprint M — move the MastekoFM Drive root into a Google Shared Drive.

Why: Service Accounts have NO Drive storage quota. They can read/write inside
a *Shared Drive* (the org owns the storage), but cannot create files in a
personal Drive. Currently MastekoFM's root lives in Marc's personal Drive,
which is why the CI E2E smoke has had to soft-pass on storageQuotaExceeded
errors. Once we move the root into a Shared Drive, the SA writes succeed
and the soft-pass becomes obsolete.

How (move-in-place — preferred):
    files.update(addParents=<shared_drive_id>, removeParents=<old_parent>,
                 supportsAllDrives=True)
    on the existing root folder.

This MOVES the existing folder (and everything inside it) into the Shared
Drive. Every file_id stays the same — so:
  * NO Firestore mass-update needed (drive_file_id, drive_folder_id all
    remain valid)
  * "Edit in Sheets" links keep working
  * Runs don't need to be backfilled

Pre-requisites (do these manually in Drive UI):
  1. Create a Shared Drive named, e.g. "MastekoFM-DEV" (and another for prod)
  2. Add yourself as Manager
  3. Add the MastekoFM service accounts as Content Manager:
       - mfm-deployer@masteko-fm.iam.gserviceaccount.com  (CI deployer)
       - <runtime-sa>@masteko-fm.iam.gserviceaccount.com  (Cloud Run worker)
  4. Make sure no Workspace org policy blocks moving folders INTO Shared Drives

Usage (dry-run by default):
    python scripts/migrate/move_to_shared_drive.py \\
        --shared-drive-id 0AB....MastekoFM_DEV         # required
        --env dev                                      # dev | prod
        # optionally:
        --source-folder-id 1abc...                     # default: read from Firestore
        --confirm                                      # actually do it
        --token <oauth_access_token>                   # default: gcloud auth

The script:
  1. Resolves the current root folder id from dev_settings/app or prod_settings/app
  2. Verifies the source folder exists and is NOT already inside a Shared Drive
  3. Verifies the target Shared Drive is reachable + the caller has Content Manager
  4. Moves the root folder via files.update
  5. Verifies the move (driveId on the folder == --shared-drive-id)
  6. Patches Firestore: settings.drive_root_in_shared_drive = True (informational)

Idempotent: re-running on an already-migrated root prints "already in
Shared Drive — nothing to do" and exits 0.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import Any

# Lazy imports so the script can print --help without google libs installed
_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
PROJECT = "masteko-fm"


def _resolve_token(arg_token: str | None) -> str:
    if arg_token:
        return arg_token
    env_token = os.environ.get("MFM_DRIVE_TOKEN")
    if env_token:
        return env_token
    # Last resort: gcloud (the caller must have an account that can edit the
    # source folder AND has Content Manager on the target Shared Drive).
    try:
        token = subprocess.check_output(
            ["gcloud", "auth", "print-access-token", "--scopes", _DRIVE_SCOPE],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        if token:
            return token
    except Exception:  # noqa: BLE001
        pass
    sys.exit(
        "ERROR: no Drive access token. Pass --token, set MFM_DRIVE_TOKEN, "
        "or 'gcloud auth login' first."
    )


def _drive_client(token: str):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(token=token, scopes=[_DRIVE_SCOPE])
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _firestore_settings(env: str) -> tuple[str, dict[str, Any]]:
    """Return (doc_path, current_settings_dict). doc_path used for the patch."""
    from google.cloud import firestore

    prefix = f"{env}_"
    db = firestore.Client(project=PROJECT)
    doc_ref = db.collection(f"{prefix}settings").document("app")
    snap = doc_ref.get()
    return doc_ref.path, (snap.to_dict() if snap.exists else {})


def _patch_firestore_settings(env: str, patch: dict[str, Any]) -> None:
    from google.cloud import firestore

    prefix = f"{env}_"
    db = firestore.Client(project=PROJECT)
    db.collection(f"{prefix}settings").document("app").set(patch, merge=True)


def main() -> int:
    p = argparse.ArgumentParser(description="Move MastekoFM Drive root into a Shared Drive (Sprint M).")
    p.add_argument("--shared-drive-id", required=True,
                   help="Target Shared Drive id (e.g. 0AB...). The root folder is moved INSIDE this drive.")
    p.add_argument("--env", choices=["dev", "prod"], required=True,
                   help="Which Firestore prefix's drive_root_folder_id to migrate.")
    p.add_argument("--source-folder-id", default=None,
                   help="Override the root folder id (default: read from Firestore settings).")
    p.add_argument("--confirm", action="store_true",
                   help="Actually do the move. Without this flag, runs as a dry run.")
    p.add_argument("--token", default=None,
                   help="OAuth access token (Drive scope). Defaults to gcloud or MFM_DRIVE_TOKEN.")
    args = p.parse_args()

    token = _resolve_token(args.token)
    drive = _drive_client(token)

    # 1. Resolve source root id
    if args.source_folder_id:
        src_id = args.source_folder_id
        print(f"Source folder (from --source-folder-id): {src_id}")
    else:
        path, current = _firestore_settings(args.env)
        src_id = current.get("drive_root_folder_id")
        if not src_id:
            print(f"ERROR: no drive_root_folder_id in {path}", file=sys.stderr)
            return 1
        print(f"Source folder (from {path}): {src_id}")

    # 2. Inspect source folder
    src = drive.files().get(
        fileId=src_id,
        fields="id,name,driveId,parents,mimeType,trashed",
        supportsAllDrives=True,
    ).execute()
    print(f"  name='{src.get('name')}'  driveId={src.get('driveId')}  parents={src.get('parents')}")
    if src.get("trashed"):
        print("ERROR: source folder is trashed", file=sys.stderr)
        return 1
    if src.get("mimeType") != "application/vnd.google-apps.folder":
        print(f"ERROR: source is not a folder (mimeType={src.get('mimeType')})", file=sys.stderr)
        return 1
    if src.get("driveId") == args.shared_drive_id:
        print(
            f"OK: source folder is already inside the target Shared Drive "
            f"({args.shared_drive_id}). Nothing to do."
        )
        return 0
    if src.get("driveId"):
        print(
            f"ERROR: source is already in a different Shared Drive ({src.get('driveId')}). "
            "Move it back to a personal Drive first, or pick that drive as --shared-drive-id.",
            file=sys.stderr,
        )
        return 1

    # 3. Inspect target Shared Drive
    try:
        td = drive.drives().get(driveId=args.shared_drive_id).execute()
        print(f"Target Shared Drive: '{td.get('name')}' ({args.shared_drive_id})")
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: cannot reach Shared Drive {args.shared_drive_id}: {exc}", file=sys.stderr)
        print("  Make sure your account is a Manager or Content Manager.", file=sys.stderr)
        return 1

    # 4. Move (or dry run)
    old_parents = ",".join(src.get("parents") or [])
    if not args.confirm:
        print()
        print("DRY RUN — would execute:")
        print("  drive.files().update(")
        print(f"    fileId='{src_id}',")
        print(f"    addParents='{args.shared_drive_id}',")
        print(f"    removeParents='{old_parents}',")
        print("    supportsAllDrives=True,")
        print("  )")
        print()
        print("Then patch Firestore: settings.drive_root_in_shared_drive = True")
        print()
        print("Re-run with --confirm to actually do it.")
        return 0

    print()
    print(f"Moving {src_id} → Shared Drive {args.shared_drive_id} …")
    moved = drive.files().update(
        fileId=src_id,
        addParents=args.shared_drive_id,
        removeParents=old_parents,
        fields="id,name,driveId,parents",
        supportsAllDrives=True,
    ).execute()
    print(f"  moved.driveId={moved.get('driveId')}")
    if moved.get("driveId") != args.shared_drive_id:
        print("ERROR: post-move driveId does not match target Shared Drive", file=sys.stderr)
        return 1

    # 5. Patch Firestore (informational flag)
    _patch_firestore_settings(args.env, {
        "drive_root_in_shared_drive": True,
        "shared_drive_id": args.shared_drive_id,
    })
    print(f"Patched {args.env}_settings/app: drive_root_in_shared_drive=True, shared_drive_id={args.shared_drive_id}")

    print()
    print("✓ Migration complete.")
    print("  Next: in CI, drop the ALLOW_SA_QUOTA_SOFT_PASS env var so")
    print("  the E2E smoke hard-fails on quota errors (which should no")
    print("  longer happen).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
