# Campus Adele seed

The 15-tab construction-to-perm financing model used to validate Sprint B's
post-cleanup architecture.

## Files

| File | Role | Description |
|---|---|---|
| `campus_adele_model.xlsx` | Model | Full 15-tab Construction-to-Perm model. 5 `I_` input tabs, 1 `O_Annual Summary` output tab, 9 calc tabs. |
| `campus_adele_base_pack.xlsx` | AssumptionPack | Only the `I_` tabs from the Model, with the Base Case values pre-filled. |
| `campus_adele_summary.xlsx` | OutputTemplate | Minimal investor summary — `M_Annual Summary` (filled by Model.O_Annual Summary) + `O_Report`. |

## Seed via API

```bash
curl -X POST <API_URL>/api/seed/campus-adele \
  -H "Authorization: Bearer <token>" \
  -H "X-MFM-Drive-Token: <google-token>"
```

Idempotent. Returns the IDs of the created Model + Project + AssumptionPack + OutputTemplate.

## Rebuild from fixture

```bash
python scripts/build_campus_adele_seed.py
```
