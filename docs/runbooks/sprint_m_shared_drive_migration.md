# Sprint M — Shared Drive migration runbook

> Move the MastekoFM Drive root from a personal Drive into a Google **Shared
> Drive** so Service Accounts can write there directly.
>
> Symptoms this fixes:
> - CI E2E "soft-pass" warnings about `storageQuotaExceeded`
> - SA-uploaded run output bytes silently dropped
> - "Run completed but `output_download_url` is null" in logs
>
> Rationale: Service Accounts have **no Drive storage quota of their own**.
> They can read/write files inside a Shared Drive (org-owned storage), but
> creating files in a *personal* Drive returns `storageQuotaExceeded` 403.

## Prerequisites

You need:

- **Manager** access to a Google Workspace that supports Shared Drives
  (any Workspace tier above Business Starter). Personal Gmail accounts
  cannot create Shared Drives.
- The MastekoFM service account emails (one for CI deploy, one for the
  Cloud Run worker if different):
  - `mfm-deployer@masteko-fm.iam.gserviceaccount.com`
  - The runtime SA used by `masteko-fm-api-{dev,prod}` Cloud Run services
    (find via `gcloud run services describe ... --format="value(spec.template.spec.serviceAccountName)"`)
- The current Drive root folder ID for both DEV and PROD (read it from
  `dev_settings/app.drive_root_folder_id` and `prod_settings/app.drive_root_folder_id`
  in Firestore, or `gcloud firestore documents get`).

## Step 1 — Create Shared Drive(s)

Two separate Shared Drives is cleanest:

```text
MastekoFM-DEV     ← used by dev_*  Firestore + masteko-fm-api-dev
MastekoFM-PROD    ← used by prod_* Firestore + masteko-fm-api-prod
```

In Google Drive:

1. Sidebar → Shared drives → **+ New** → name it `MastekoFM-DEV`
2. **+ Manage members** → add yourself as **Manager**
3. Add the deployer SA as **Content Manager**:
   `mfm-deployer@masteko-fm.iam.gserviceaccount.com`
4. Add the runtime SA(s) as **Content Manager** (same address may apply to both)
5. Repeat for `MastekoFM-PROD`

Capture the Shared Drive IDs (the URL after `/drive/folders/` when you click
the drive). They look like `0AB...`.

## Step 2 — Move the existing root folder INTO the Shared Drive

The whole tree comes along. Every file ID stays the same — no Firestore
mass-update needed, "Edit in Sheets" links keep working, runs don't need
backfill.

```bash
# Dry run first (always)
python scripts/migrate/move_to_shared_drive.py \
    --shared-drive-id 0AB...DEV \
    --env dev

# Execute
python scripts/migrate/move_to_shared_drive.py \
    --shared-drive-id 0AB...DEV \
    --env dev \
    --confirm

# Repeat for prod
python scripts/migrate/move_to_shared_drive.py \
    --shared-drive-id 0AB...PROD \
    --env prod \
    --confirm
```

The script:

1. Reads the current `drive_root_folder_id` from `{env}_settings/app`
2. Verifies it's NOT already in a Shared Drive
3. Verifies the target Shared Drive is reachable + you have Content Manager
4. Calls `drive.files().update(addParents=<shared_drive>, removeParents=<old>)`
5. Confirms `driveId` on the folder == target after the move
6. Patches `{env}_settings/app` with `drive_root_in_shared_drive=True` and
   `shared_drive_id=<id>` (informational; nothing reads these yet)

**Idempotent**: re-running on an already-migrated root prints
"already in Shared Drive — nothing to do" and exits 0.

## Step 3 — Drop the soft-pass from CI

Edit `.github/workflows/deploy-dev.yml` and remove this env var from the
"E2E smoke" step:

```yaml
ALLOW_SA_QUOTA_SOFT_PASS: "1"   # ← delete this line after migration
```

After this change, the next CI E2E will hard-fail if any
`storageQuotaExceeded` ever happens — which it shouldn't, because the SA
can now write directly to the Shared Drive.

## Step 4 — Verify

1. Check the Drive UI: the MastekoFM root folder is now under
   `Shared drives → MastekoFM-DEV` (or PROD). Old "open in Drive" links
   continue to work.
2. Open the deployed app, run Hello World. Expected:
   - Run completes
   - Run output xlsx + PDF appear in the Run's per-run folder under the
     Shared Drive
   - "Open in Sheets" + "📄 PDF" + "📜 Narrative" + "📁 Folder" links
     all work
3. Trigger a manual `Deploy DEV` run. The E2E smoke should:
   - Succeed at the run step (no soft-pass warning)
   - Download the output xlsx
   - Assert Sum=12 / Product=35 / Total=47

If anything fails: re-add `ALLOW_SA_QUOTA_SOFT_PASS: "1"` to the workflow,
investigate, and re-attempt.

## Rollback

The migration is reversible by moving the folder back out:

```bash
# In Drive UI: drag the root folder out of the Shared Drive into "My Drive"
# Or programmatically via files.update(addParents=<my-drive-folder>,
#                                       removeParents=<shared-drive-id>)
```

File IDs are still preserved — Firestore needs no rollback either. Restore
the `ALLOW_SA_QUOTA_SOFT_PASS: "1"` env var in CI to keep deploys green
while you investigate.

## Why move-in-place (not copy)?

The script uses `files.update(addParents=..., removeParents=...)` — this
**moves** the existing folder into the Shared Drive. Every file's ID is
preserved. The alternative — copying every file into a fresh tree — would
require a Firestore mass-update of every `drive_file_id` and
`drive_folder_id`, plus old "Edit in Sheets" URLs would 404.

Move-in-place is reversible, idempotent, and zero-data-migration. Costs
nothing. Use this every time.

## Org policy gotcha

Some Google Workspace policies block moving folders **into** a Shared Drive,
or restrict moving Google-native files into a different ownership context.
If the script's `files.update` returns `cannotMoveTrashedItem` or similar,
check Workspace Admin Console → Drive and Docs → Sharing settings →
"Allow users to move content from My Drive to Shared drives" → **must be
enabled**.
