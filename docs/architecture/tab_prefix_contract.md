# Tab-prefix contract

> The convention every `.xlsx` file in MastekoFM must obey.
> Audience: Model authors, OutputTemplate authors, engine developers.

---

## The four prefixes

Every tab (worksheet) in any MastekoFM-managed `.xlsx` is one of:

| Prefix | Type | Used on | Filled by | Read by |
|---|---|---|---|---|
| `I_*` | Input | Model, AssumptionPack | AssumptionPack | Model formulas |
| `O_*` | Output | Model | Model formulas | OutputTemplate, Run output |
| `M_*` | Model-output input | OutputTemplate | Model `O_*` values | OutputTemplate formulas |
| (no prefix) | Calculation | Model, OutputTemplate | Author at design time | self / next stage |

**Strict case sensitivity.** `I_Inputs` is an input. `i_Inputs` is a calc tab. `INPUT_Inputs` is a calc tab. The validator uses literal `str.startswith("I_")` checks.

---

## Per-entity rules

### AssumptionPack `.xlsx`

- ✅ MUST contain only `I_*` tabs
- ❌ MUST NOT contain `O_*` tabs
- ❌ MUST NOT contain `M_*` tabs
- ❌ MUST NOT contain calc tabs

A valid AssumptionPack is the smallest possible file: just the input tabs the user is responsible for, with their values.

### Model `.xlsx`

- ✅ MUST contain at least one `I_*` tab
- ✅ MUST contain at least one `O_*` tab
- ✅ MAY contain any number of calc tabs (typically several)
- ❌ MUST NOT contain `M_*` tabs (those are exclusively for OutputTemplates)

A Model declares its required inputs (the `I_*` tab list) and its published outputs (the `O_*` tab list).

### OutputTemplate `.xlsx`

- ✅ MAY contain `M_*` tabs (cells that get filled with Model `O_*` values)
- ✅ MUST contain at least one `O_*` tab (the final user-facing output)
- ✅ MAY contain any number of calc tabs
- ❌ MUST NOT contain `I_*` tabs (OutputTemplates don't take user input directly)

For OutputTemplates with format != `xlsx` (PDF/Word/Google Doc), the prefix rules don't apply — those use placeholder substitution instead.

---

## Naming conventions for tab basenames

Stripped prefix is the "basename". Examples:

| Tab | Prefix | Basename |
|---|---|---|
| `I_Inputs & Assumptions` | `I_` | `Inputs & Assumptions` |
| `I_Budget Input Data` | `I_` | `Budget Input Data` |
| `O_Annual Summary` | `O_` | `Annual Summary` |
| `M_Annual Summary` | `M_` | `Annual Summary` |

**Cross-stage matching uses basenames.**

- AssumptionPack `I_Inputs & Assumptions` matches Model `I_Inputs & Assumptions` (same name, same prefix — direct overlay)
- Model `O_Annual Summary` provides values for OutputTemplate `M_Annual Summary` (same basename, prefix swap)

---

## Cell-level conventions

The engine doesn't enforce these, but template authors should follow:

### Within `I_*` tabs (Model side)

Cells should be **literals, not formulas**. The whole point is for AssumptionPacks to overlay these.

If a cell on `I_*` contains a formula referencing a calc tab (e.g., `='Sources & Uses - Construction'!A4`), it'll show `#REF!` when the AssumptionPack is opened standalone in Drive. The formula resolves correctly at calc time once overlaid into the Model — but it's UX noise for the user editing the AssumptionPack.

**Recommendation**: keep `I_*` tabs as literal-only. If you need a derived display, put it on a calc tab.

### Within calc tabs

Reference other tabs by their full name with a prefix: `=I_Inputs!B5`, `=Calc!A3`. Avoid:

- ❌ Sheet-index references — order may shift across versions
- ❌ Implicit current-sheet references in cross-sheet formulas
- ❌ Array formulas in `I_*` or `M_*` tabs (overlay treats them inconsistently)
- ❌ Pivot tables in `I_*` or `M_*` tabs (similar issue)

### Within `O_*` tabs (Model side)

Output tabs should be **formula-driven**, computing from calc tabs. The OutputTemplate consumes their resolved values.

The shape of `O_*` matters: an OutputTemplate's matching `M_*` tab will have the same dimensions and read by cell reference (e.g., `=M_Annual Summary!B5`). If you change the row order in `O_*`, downstream OutputTemplates may break. Treat `O_*` shape as part of the Model's public API.

### Within `M_*` tabs (OutputTemplate side)

These are the "input from Model" tabs. They start with placeholder values (often zero or empty). The engine fills them at run time.

You can wire OutputTemplate's calc tabs to read from `M_*` directly: `=M_Annual Summary!B5`. The OutputTemplate's formulas re-evaluate after the M_ values are injected.

---

## Validator behavior

`services/excel_template_engine.classify_tabs()` returns:

```python
{
    "input_tabs":  [str],   # tabs starting with "I_"
    "output_tabs": [str],   # tabs starting with "O_"
    "m_tabs":      [str],   # tabs starting with "M_"
    "calc_tabs":   [str],   # everything else
}
```

`validate_template(wb, role)` returns a list of error strings. Empty list = valid. The role determines what's allowed:

- `role="model"` — must have ≥1 I_ and ≥1 O_; must not have M_
- `role="assumption_pack"` — must have only I_
- `role="output_template_xlsx"` — must have ≥1 O_; may have M_ and calc; must not have I_

---

## Edge cases the engine handles

| Edge case | Behavior |
|---|---|
| Empty workbook | Validation error: "No input tabs declared" (or similar role-specific) |
| Tab name with leading dot (`.hidden`) | Excel rejects on save; validator surfaces clearer error |
| Mixed case prefixes (`i_Foo`, `o_Bar`) | Treated as calc tabs; not warned (could be a future lint rule) |
| Tab named exactly `I_` (no basename) | Treated as input with empty basename; matched by basename means it pairs only with another `I_` of the same — fine but pointless |
| MergedCells in destination | Engine unmerges before overlay, re-applies source merges after |
| Source tab smaller than destination | Engine clears destination cells within source's used range to prevent stale data |
| Source tab larger than destination | Engine writes everything; destination grows |
| Cross-sheet formulas in calc tabs that reference an overlaid I_ tab | Resolve correctly post-overlay (proven on Campus Adele's 7,302 calc-tab formulas) |

---

## Future extensions (not yet implemented)

- **`H_*` (Hidden helper) prefix** — for tabs that are calc but should be hidden in the rendered output. Useful when an OutputTemplate has intermediate calculations that shouldn't appear in the final report. For now, just hide them in Excel manually.
- **Per-cell metadata via comments** — declare cell types (currency, percent), units, validation ranges. Speculative; only if there's pull.
- **Template lint** — a CI job that opens every Model in `seed/` and warns about cross-tab refs in `I_*`, missing `O_*` declarations, etc.
