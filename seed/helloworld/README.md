# Hello World seed

Three tiny `.xlsx` files that exercise the entire MastekoFM run pipeline end-to-end. The smallest non-trivial example of three-way composition.

## Files

### `helloworld_model.xlsx` — the Model

| Tab | Contents |
|---|---|
| `I_Numbers` | A1=`a`, B1=`2` (placeholder); A2=`b`, B2=`3` |
| `Calc` | A1=`=I_Numbers!B1+I_Numbers!B2`; A2=`=I_Numbers!B1*I_Numbers!B2` |
| `O_Results` | A1=`sum`, B1=`=Calc!A1`; A2=`product`, B2=`=Calc!A2` |

### `helloworld_inputs.xlsx` — the AssumptionPack

| Tab | Contents |
|---|---|
| `I_Numbers` | A1=`a`, B1=**5**; A2=`b`, B2=**7** |

(only the `I_*` tab — no calc, no outputs)

### `helloworld_report.xlsx` — the OutputTemplate

| Tab | Contents |
|---|---|
| `M_Results` | A1=`sum`, B1=`0` (placeholder); A2=`product`, B2=`0` |
| `O_Report` | A1=`Hello World Report` (merged A1:B1)<br>A3=`Sum:`, B3=`=M_Results!B1`<br>A4=`Product:`, B4=`=M_Results!B2`<br>A5=`Total:`, B5=`=M_Results!B1+M_Results!B2` |

## Expected Run output

When `(helloworld_inputs × helloworld_model × helloworld_report)` is run:

```
O_Report:
  A1: Hello World Report
  A3: Sum:        B3: 12     ← 5 + 7
  A4: Product:    B4: 35     ← 5 × 7
  A5: Total:      B5: 47     ← 12 + 35
```

If those numbers come out, the engine is working end-to-end.

## How to seed

```bash
curl -X POST <API_URL>/api/seed/helloworld -H "Authorization: Bearer <token>"
```

Idempotent — running twice returns the existing IDs.

## How to rebuild these files

```bash
python scripts/build_helloworld_seed.py
```

Don't hand-edit the `.xlsx` files — re-run the script if you need to change them so the file format stays clean.
