# Run pipeline

> How a Run executes from POST to artifact.

---

## Two-stage execution

Every Run is a two-stage overlay-recalc, regardless of which Model and OutputTemplate are involved:

```
Stage 1 — Model
  Inputs:  Model.xlsx + AssumptionPack.xlsx
  1. Open Model.xlsx
  2. For each I_<name> tab in Model:
       overlay AssumptionPack.I_<name> cells onto Model.I_<name>
  3. LibreOffice recalc the merged Model
  4. Read all O_<name> tab cell values into a dict

  Output: { tab_name → {cell_ref → value} }

Stage 2 — OutputTemplate
  Inputs:  OutputTemplate.xlsx + Stage 1 output dict
  1. Open OutputTemplate.xlsx
  2. For each M_<name> tab in OutputTemplate:
       inject Model's O_<name> values into matching cells
  3. LibreOffice recalc the OutputTemplate
  4. Save the recalculated OutputTemplate as the final artifact

  Output: artifact bytes
```

For OutputTemplates with format != `xlsx`, Stage 2 substitutes a renderer (PDF/Word/GoogleDoc) that reads the Stage 1 output dict and produces the artifact directly.

---

## Algorithm (canonical)

```python
def execute_run(run: Run) -> RunResult:
    # 1. Load all three artifacts at the recorded versions
    model_bytes  = drive.download(run.model_drive_file_id, revision=run.model_drive_revision_id)
    pack_bytes   = drive.download(run.pack_drive_file_id,  revision=run.pack_drive_revision_id)
    template     = load_template(run.output_template_id, run.output_template_version)
    
    # 2. Validate compatibility (defensive — UI also gates, but never trust it)
    errors = run_validator.validate(
        model=parse_model(model_bytes),
        pack=parse_pack(pack_bytes),
        output_template=template,
    )
    if errors:
        raise IncompatibleComposition(errors)
    
    # 3. Stage 1 — overlay pack onto model, recalc model
    merged_model_bytes, warnings_1 = overlay_pack_onto_model(model_bytes, pack_bytes)
    recalced_model_bytes = libreoffice_recalc(merged_model_bytes)  # ~10-20s for Campus Adele
    
    # 4. Extract Model O_* tab values
    model_outputs = extract_model_outputs(recalced_model_bytes)
    # model_outputs = {"O_Annual Summary": {"A1": "Item", "B1": 12345, ...}, ...}
    
    # 5. Stage 2 — render output via the right renderer for the template's format
    if template.format == "xlsx":
        artifact_bytes = xlsx_renderer.render(template, model_outputs)
    elif template.format == "pdf":
        artifact_bytes = pdf_renderer.render(template, model_outputs)
    elif template.format == "docx":
        artifact_bytes = docx_renderer.render(template, model_outputs)
    elif template.format == "google_doc":
        artifact_bytes = gdoc_renderer.render(template, model_outputs)
    else:
        raise UnknownFormat(template.format)
    
    # 6. Upload to GCS (stable URL) + Drive (visibility)
    gcs_path = f"runs/{run.id}/{timestamp}_{template.format_extension}"
    download_url = storage_service.upload(gcs_path, artifact_bytes)
    drive_file_id = drive.upload(
        folder=run.project.drive_folders.outputs,
        filename=f"{timestamp}_{run.id}.{template.format_extension}",
        content=artifact_bytes,
    )
    
    # 7. Return result
    return RunResult(
        status="completed",
        warnings=warnings_1 + warnings_2,
        output_gcs_path=gcs_path,
        output_download_url=download_url,
        output_drive_file_id=drive_file_id,
    )
```

---

## xlsx renderer (the canonical case — same engine reused)

```python
def render_xlsx(template, model_outputs):
    # OutputTemplate is itself an .xlsx — reuse the engine.
    template_bytes = drive.download(template.drive_file_id, revision=template.drive_revision_id)
    
    # Build a synthetic "AssumptionPack-shaped" file from model_outputs:
    # for each O_<name> in model_outputs, create an I_<name> tab with the values.
    # But the OutputTemplate expects M_<name> tabs to be filled, not I_<name>.
    # So we directly inject into M_<name> tabs in the template.
    
    wb = openpyxl.load_workbook(io.BytesIO(template_bytes))
    for m_tab in template.m_tabs:
        basename = m_tab.removeprefix("M_")
        source_o_tab = f"O_{basename}"
        if source_o_tab not in model_outputs:
            continue  # validator should have caught this; defensive skip
        cell_values = model_outputs[source_o_tab]
        for cell_ref, value in cell_values.items():
            try:
                wb[m_tab][cell_ref].value = value
            except (AttributeError, ValueError):
                pass  # MergedCell or invalid; defensive
    
    buf = io.BytesIO()
    wb.save(buf)
    
    # Recalc the OutputTemplate so its calc + O_ tabs reflect the injected values
    return libreoffice_recalc(buf.getvalue())
```

For non-xlsx renderers (PDF/Word/GoogleDoc), the model_outputs dict drives placeholder substitution instead.

---

## Performance characteristics

Measured on the live DEV (Campus Adele model, Drive-backed):

| Step | Time |
|---|---|
| Drive download (Model + Pack) | ~1.5s |
| Stage 1 overlay (openpyxl cell-copy) | ~0.5s |
| Stage 1 LibreOffice recalc (15-tab model, 7,302+493 formulas) | ~10s |
| Stage 1 extract O_ tabs | ~0.3s |
| Stage 2 inject + recalc (small OutputTemplate) | ~3s |
| Stage 2 GCS + Drive upload | ~1s |
| **Total** | **~16-18s** |

Hello World end-to-end: estimated <2s.

Targets for Sprint C (async + worker tuning):
- Time-to-202 (POST returns): <500ms
- p50 Run completion (Hello World): <3s
- p50 Run completion (Campus Adele full): <20s
- Concurrency: 10 simultaneous Runs without degradation

---

## Failure modes & retries

| Failure | Detection | Recovery |
|---|---|---|
| Drive download 401 | OAuth token expired | Worker fails the Run; user re-signs in and retries via UI |
| Drive download 404 | File deleted between Run create and execution | Worker fails with "Source file no longer available" |
| LibreOffice timeout (>60s/stage) | subprocess TimeoutExpired | Worker fails with timeout error; user can retry |
| LibreOffice crash | non-zero exit | Worker fails; Cloud Tasks retries up to 3x with backoff |
| openpyxl read error (corrupt .xlsx) | exception during load | Worker fails immediately, no retry |
| Compatibility violation | `run_validator.validate` returns errors | Worker fails immediately, no retry; user fixes pack/template |
| GCS upload error | exception | Worker fails; Cloud Tasks retries |
| Out-of-memory | container OOMKilled | Cloud Tasks retries on a fresh container |

Cloud Tasks retry policy:
- Max attempts: 3
- Initial backoff: 30s
- Max backoff: 5 min
- Backoff multiplier: 2

After final failure, the Run sits with `status=failed` and the user can manually retry via the UI (creates a new Run with the same composition).

---

## Cancellation

When the UI cancels a Run:
1. Frontend POSTs `/api/runs/{id}/cancel`
2. Backend sets `status=cancelled` on the Firestore doc
3. Worker checks Firestore status before each major step; if cancelled, exits cleanly without uploading

This is best-effort — a Run already in LibreOffice subprocess can't be killed mid-flight without losing the container. Acceptable for now.

---

## Idempotency

Each Cloud Task carries the `run_id`. The worker:
1. Reads the Run doc
2. If `status` is already `running` (and started_at is recent), assumes another worker has it. Skips.
3. If `status` is `completed` or `failed`, returns success immediately (Cloud Task is acked).
4. If `status` is `pending`, sets to `running` with started_at and proceeds.

This protects against Cloud Tasks delivering the same task twice (which can happen).

---

## Observability

Every Run logs:
- Stage timings (download, overlay, recalc, extract, render, upload)
- LibreOffice exit codes and stderr (for debugging recalc failures)
- Compatibility validator error list (if pre-execution validation fails)
- Drive revision IDs of all source files
- Final output size in bytes

Future: surface stage timings as a histogram per Model in the Runs dashboard. Sprint G+.
