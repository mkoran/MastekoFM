# `seed/` — Committed seed files

`.xlsx` (and later `.docx`, `.zip`, etc.) files committed to the repo so any deploy can re-seed a fresh DEV environment with the same data. Each subdirectory is one "scenario" the platform demonstrates.

| Subdirectory | Purpose | Used by | Created in |
|---|---|---|---|
| `helloworld/` | Tiniest possible 3-way example. Verifies the engine end-to-end. | `/api/seed/helloworld` (Sprint A); `tests/fixtures/` mirror | Sprint A |
| `campus_adele/` | The real 15-tab construction-to-perm financing model. | `/api/seed/campus-adele` (Sprint B rewrite); regression tests | Sprint B |

## Convention

Each scenario contains:

```
<scenario>/
├── README.md                                 -- explains the file structure
├── <scenario>_model.xlsx                     -- the Model
├── <scenario>_<packname>_pack.xlsx           -- one or more AssumptionPacks
└── <scenario>_<templatename>.<ext>           -- one or more OutputTemplates
                                                  (.xlsx, or for PDF: subdir/)
```

## How to use

In any environment (LOCAL / DEV / PROD):

```bash
# Hello World
curl -X POST <API_URL>/api/seed/helloworld \
  -H "Authorization: Bearer <token>"

# Campus Adele (Sprint B+)
curl -X POST <API_URL>/api/seed/campus-adele \
  -H "Authorization: Bearer <token>" \
  -H "X-MFM-Drive-Token: <google-token>"
```

Seeds are **idempotent** — running twice returns the existing IDs rather than creating duplicates.

## Why files are committed (not generated)

So a brand-new DEV after a Firestore wipe can be re-seeded with the same canonical inputs without depending on Marc's local machine. So tests have realistic fixtures. So a new dev can `git clone` and immediately understand the entity shapes by opening the .xlsx files in Excel.
