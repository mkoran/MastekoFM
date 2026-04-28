# Sprint H — Word + Google Docs OutputTemplates

> Estimated: ~4-5 days
> Branch: `epic/sprint-h-word-gdoc`
> Goal: third and fourth output formats (`.docx` and Google Doc).
> Blocked-by: Sprint D

---

## Why

xlsx + PDF cover most use cases, but lender packages often want native Word; team collaboration sometimes wants live Google Docs. Same architectural pattern: another renderer behind the existing `OutputTemplate.format` field.

---

## Definition of Done

- OutputTemplate.format accepts `"docx"` and `"google_doc"`
- python-docx renderer reads .docx with `{{ binding }}` placeholders → produces .docx
- Google Docs renderer copies a template Doc → fills placeholders via Docs API → produces a real Google Doc in user's Drive
- Format-aware upload UI per template type
- Seed: Campus Adele lender package (.docx) + investor briefing (Google Doc)
- Tests: both renderers end-to-end with Hello World

---

## Stories

### H-001 · python-docx dep (XS)

Add to `backend/requirements.txt`:
```
python-docx>=1.1.0,<2.0.0
```

### H-002 · docx renderer (M)

`services/output_renderers/docx_renderer.py`:
```python
from docx import Document

def render_docx(template_bytes: bytes, model_outputs: dict) -> bytes:
    doc = Document(io.BytesIO(template_bytes))
    
    # Substitute placeholders in paragraphs and tables
    for paragraph in doc.paragraphs:
        for key, value in flatten_outputs(model_outputs).items():
            placeholder = "{{ " + key + " }}"
            if placeholder in paragraph.text:
                # Use run-level edits to preserve formatting
                replace_in_runs(paragraph, placeholder, str(value))
    
    for table in doc.tables:
        for cell in iterate_cells(table):
            for paragraph in cell.paragraphs:
                # Same substitution
                ...
    
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
```

`flatten_outputs` turns `{"O_Annual Summary": {"B5": 12345}}` into `{"O_Annual_Summary.B5": 12345}` so placeholders are flat.

### H-003 · OutputTemplate.format = "docx" (S)

Storage: Drive `.docx` file. Validator: open with python-docx, scan for `{{ ... }}` placeholders, store the binding list.

### H-004 · Campus Adele lender_package.docx (S)

Build in Word (or via python-docx in a script). Cover page, project info, financials section with placeholders. Commit to `seed/campus_adele/lender_package.docx`.

### H-005 · Google Docs API client (XS)

Already enabled (Sprint A OAuth setup). `pip install google-api-python-client` already there.

### H-006 · Google Doc renderer (M)

`services/output_renderers/gdoc_renderer.py`:
```python
def render_gdoc(template_doc_id: str, model_outputs: dict, user_token: str, output_folder_id: str) -> str:
    """Returns the new Doc's file_id."""
    docs_service = build("docs", "v1", credentials=Credentials(user_token))
    drive_service = build("drive", "v3", credentials=Credentials(user_token))
    
    # 1. Copy the template Doc to a new file in output_folder
    new_file = drive_service.files().copy(
        fileId=template_doc_id,
        body={"name": f"...", "parents": [output_folder_id]},
    ).execute()
    new_id = new_file["id"]
    
    # 2. Build batchUpdate requests to replace each {{ binding }} with its value
    requests = []
    for key, value in flatten_outputs(model_outputs).items():
        requests.append({
            "replaceAllText": {
                "containsText": {"text": "{{ " + key + " }}"},
                "replaceText": str(value),
            }
        })
    docs_service.documents().batchUpdate(documentId=new_id, body={"requests": requests}).execute()
    
    return new_id
```

User sees the resulting Doc in their Drive. Run record stores the Doc's file_id and shareable URL.

### H-007 · OutputTemplate.format = "google_doc" (S)

Storage: a Google Doc file_id (the template Doc lives in user's Drive, copied per Run). Upload UI lets user paste a Doc URL; backend extracts file_id and validates by reading the Doc's text for `{{ ... }}` placeholders.

### H-008 · Frontend format-aware upload UI (S)

Single "New OutputTemplate" form. Format dropdown changes the rest:
- xlsx → file upload (.xlsx)
- pdf → file upload (.zip)
- docx → file upload (.docx)
- google_doc → text input (Doc URL or file_id)

Validation per format runs server-side on upload.

### H-009 · Tests (S)

`tests/test_docx_renderer.py` + `tests/test_gdoc_renderer.py`. For Google Doc, mock the Docs API client (don't hit production).

---

## Risks

| Risk | Mitigation |
|---|---|
| python-docx loses formatting on substitution if placeholder spans multiple runs | Use `python-docx-template` (jinja-style) which handles this; or normalize runs before substitution |
| Google Docs API quotas | Per-request batching; rate-limit per user |
| Google Doc template needs to be in user's Drive (not service account) | Yes — that's a feature, not a bug. User owns the template; we just copy. Document this. |
| Numeric formatting inconsistent across renderers | Centralize formatting helpers in `services/output_renderers/format_helpers.py` |
