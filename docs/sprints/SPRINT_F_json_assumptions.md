# Sprint F — JSON AssumptionPacks + Airtable connector

> Estimated: ~6-8 days
> Branch: `epic/sprint-f-json`
> Goal: support non-Excel data sources. Models declare key→cell binding; Airtable as first connector.
> Blocked-by: Sprint B

---

## Why

Sprints A–E shipped .xlsx-only AssumptionPacks. JSON unlocks:
- Programmatic AssumptionPack creation (sweeps, API ingestion, manual forms)
- Airtable, Google Sheets, REST API as data sources
- Smaller payloads for partial updates

---

## Definition of Done

- Model can declare an `input_schema: [{key, cell_ref, tab, type, label}]`
- AssumptionPack.format = `"xlsx" | "json"`; backend accepts both
- JSON pack stored as Firestore doc (small) OR Drive `.json` file (large)
- run_executor's Stage 1 supports both formats
- Airtable connector: configure API key + base + table → sync to a versioned JSON pack
- Manual form UI: auto-generated from Model.input_schema for quick edits
- Tests cover JSON injection + Airtable sync (mocked API)

---

## Stories

### F-001 · Model.input_schema (S)

```python
class InputBinding(BaseModel):
    key: str                  # "construction_duration"
    tab: str                  # "I_Inputs & Assumptions"
    cell_ref: str             # "B8"
    type: Literal["number", "currency", "percentage", "date", "text", "boolean"]
    label: str                # "Construction Duration (months)"
    default: Any | None
    required: bool = False

class Model:
    ...existing fields...
    input_schema: list[InputBinding]
```

For .xlsx packs, this is informational. For JSON packs, it's the binding map.

### F-002 · AssumptionPack.format field (XS)

```python
class AssumptionPack:
    format: Literal["xlsx", "json"]
    # xlsx: drive_file_id required
    # json: data dict in Firestore (≤1MB) or drive_file_id pointing to .json
```

### F-003 · JSON pack storage (S)

For small packs (<100KB): store the JSON dict directly on the Firestore doc:
```python
class AssumptionPack:
    json_data: dict | None  # for format=json + small enough
```

For large: `drive_file_id` pointing to a `.json` file in Drive.

Sync versions: every update creates a new `version` and (optionally) a new Drive revision.

### F-004 · run_executor JSON path (M)

Stage 1 changes:
```python
def stage_1(model: Model, pack: AssumptionPack) -> bytes:
    model_bytes = drive.download(model.drive_file_id)
    
    if pack.format == "xlsx":
        # Existing path
        merged = engine.overlay_scenario_on_template(model_bytes, pack.bytes)
    elif pack.format == "json":
        # Inject by binding
        wb = openpyxl.load_workbook(io.BytesIO(model_bytes))
        for binding in model.input_schema:
            value = pack.json_data.get(binding.key, binding.default)
            if value is None and binding.required:
                raise ValueError(f"Required input {binding.key} not provided")
            wb[binding.tab][binding.cell_ref] = value
        merged = save_to_bytes(wb)
    
    return libreoffice_recalc(merged)
```

### F-005 · Frontend Input Schema editor (M)

Per-Model "Input Schema" tab:
- Table: key, tab, cell_ref, type, label, required, default
- Add/edit/delete rows
- "Auto-detect" button: scans the Model's I_ tabs for cells with literal values, suggests bindings

Saved with the Model entity.

### F-006 · Frontend "New JSON pack" form (M)

Auto-generated from Model.input_schema:
- One input per binding, typed (number/text/date)
- Validation on the client + server
- Save → creates JSON pack
- Edit → bumps pack.version

### F-007 · Airtable connector service (L)

`services/connectors/airtable.py`:
```python
def sync_airtable_to_pack(
    config: AirtableConfig,
    model_input_schema: list[InputBinding],
    target_pack_id: str,
):
    # 1. Fetch Airtable base/table via API (use stored Secret Manager API key)
    # 2. Map Airtable fields to InputBinding.key by user-defined mapping
    # 3. Build dict {key: value}
    # 4. Update or create AssumptionPack (json format) with new version
```

`AirtableConfig`:
- base_id
- table_name
- api_key_secret_name  # ref to Secret Manager
- field_mappings: [{airtable_field, schema_key, transform}]

### F-008 · Connector config UI (M)

Per-Project "Connectors" tab:
- Add Airtable connector: base ID, API key (sent to backend, stored in Secret Manager), table picker, field mappings
- Test connection
- "Sync now" button + sync history

### F-009 · Scheduled sync (M)

Cloud Scheduler hits `/internal/connectors/sync/{connector_id}` on a cron. Worker handles like a Run task.

### F-010 · Tests: JSON pack injection (S)

Hello World gets an `input_schema` declaration. Test that a JSON pack `{a: 5, b: 7}` produces same output as the xlsx pack.

### F-011 · Tests: Airtable connector (M)

Mock Airtable API responses. Test full sync flow → JSON pack updated correctly.

---

## Risks

| Risk | Mitigation |
|---|---|
| Model schema drift breaks existing JSON packs | Validate on Run launch; surface "key X removed from Model schema, value will be ignored" warnings |
| Airtable API rate limits | Batch reads; back off on 429 |
| Type coercion errors (string "5" vs number 5) | Explicit type field on InputBinding; cast before injection |
| User accidentally deletes a binding | Confirm dialog + audit log |
