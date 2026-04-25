# Sprint D — PDF OutputTemplates

> Estimated: ~2-3 days
> Branch: `epic/sprint-d-pdf`
> Goal: render OutputTemplates as branded PDFs via WeasyPrint. First investor summary for Campus Adele.
> Blocked-by: Sprint B
> Can run in parallel with: Sprint C

---

## Why

The xlsx OutputTemplate from Sprint A is functional but ugly for stakeholder reports. PDF is the format users actually want for "Investor Summary one-pager", "Lender Package", etc.

---

## Definition of Done

- OutputTemplate.format = `"pdf"` accepted by upload endpoint
- HTML/CSS template format defined: a `.zip` containing `template.html`, `template.css`, optional `assets/` (logos, fonts)
- WeasyPrint renderer produces real PDFs from template + Model output dict
- A "Campus Adele Investor Summary" PDF template is committed to `seed/campus_adele/investor_summary/`
- User can upload PDF templates via UI
- Run with format=pdf produces a downloadable .pdf
- PDF renders within 60s

---

## Stories

### D-001 · WeasyPrint dep (XS)

Add to `backend/requirements.txt`:
```
weasyprint>=62.0,<63.0
```

WeasyPrint requires system libs (cairo, pango, gdk-pixbuf). Add to `backend/Dockerfile`:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf2.0-0 fonts-liberation \
 && rm -rf /var/lib/apt/lists/*
```

### D-002 · OutputTemplate.format field (XS)

Add `format: Literal["xlsx", "pdf"] = "xlsx"` to OutputTemplate model. Storage path / file extension chosen accordingly.

### D-003 · `services/output_renderers/pdf_renderer.py` (M)

```python
import jinja2, weasyprint
def render_pdf(template_zip_bytes: bytes, model_outputs: dict) -> bytes:
    # 1. Unzip template into temp dir
    # 2. Load template.html, render with Jinja2 using model_outputs as context
    # 3. WeasyPrint(html_string, base_url=tempdir).write_pdf()
    return pdf_bytes
```

Jinja2 context provides:
- `model.O_<name>.<cell_ref>` — values from each O_ tab
- `now` — render timestamp
- `run.id`, `run.triggered_by`

### D-004 · OutputTemplate as `.zip` (S)

PDF templates are uploaded as `.zip`. Validator checks:
- Contains `template.html`
- HTML uses Jinja2 syntax `{{ model.O_xxx.B5 }}` for bindings
- Optional `template.css` for styling

The `m_tabs` field becomes irrelevant for PDF (no tab structure). Store the binding list parsed from `{{ ... }}` placeholders for compatibility validation.

### D-005 · run_executor format dispatch (S)

`run_executor.execute_run_sync()` branches on `output_template.format`:
```python
if format == "xlsx":  return xlsx_renderer.render(...)
if format == "pdf":   return pdf_renderer.render(...)
```

### D-006 · Campus Adele Investor Summary template (M)

`seed/campus_adele/investor_summary/`:
- `template.html` — cover page, project info, key metrics table (IRR, NPV, equity multiple), 12-month proforma snippet
- `template.css` — branded fonts, colors
- `assets/logo.png` — placeholder
- `README.md`

### D-007 · Frontend: PDF template upload UI (S)

OutputTemplate upload form gets a format dropdown. PDF format accepts `.zip`. Show a list of declared `{{ ... }}` bindings and warn if any aren't matched by the selected Model.

### D-008 · Test (S)

`tests/test_pdf_renderer.py`:
- Render Hello World PDF (with a tiny PDF template) → assert PDF starts with `%PDF-`
- Render Campus Adele PDF → assert file size reasonable + first-page render contains expected text (use pypdf to extract)

---

## Risks

| Risk | Mitigation |
|---|---|
| WeasyPrint OOMs on complex layouts | Cap concurrent PDF renders per worker; profile with realistic templates |
| Fonts missing in Cloud Run container | Bundle Liberation fonts; declare in CSS as fallback |
| Charts in PDF (currently no chart support) | Phase 2: matplotlib → PNG → embed; or HTML/CSS charts via Chart.js + WeasyPrint's JS limitation (pre-render needed) |
| HTML templates break on edge content | Sanitize via Jinja2 autoescape |
