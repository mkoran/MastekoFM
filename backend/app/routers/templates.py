"""Templates router — CRUD and apply for assumption templates."""
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.models.template import TemplateCreate, TemplateResponse

router = APIRouter(tags=["templates"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def _templates_ref():
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}assumption_templates")


def _to_response(doc_id: str, data: dict[str, Any]) -> TemplateResponse:
    return TemplateResponse(
        id=doc_id,
        name=data.get("name", ""),
        description=data.get("description", ""),
        key_values=data.get("key_values", []),
        tables=data.get("tables", []),
        created_by=data.get("created_by", ""),
        created_at=data.get("created_at", datetime.now(UTC)),
        updated_at=data.get("updated_at", datetime.now(UTC)),
    )


@router.get("/api/templates", response_model=list[TemplateResponse])
async def list_templates(current_user: CurrentUser):
    """List all available assumption templates."""
    docs = _templates_ref().stream()
    return [_to_response(doc.id, doc.to_dict()) for doc in docs]


@router.get("/api/templates/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: str, current_user: CurrentUser):
    """Get a single template."""
    doc = _templates_ref().document(template_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Template not found")
    return _to_response(doc.id, doc.to_dict())


@router.post("/api/templates", response_model=TemplateResponse, status_code=201)
async def create_template(body: TemplateCreate, current_user: CurrentUser):
    """Create a new assumption template."""
    now = datetime.now(UTC)
    data = {
        "name": body.name,
        "description": body.description,
        "key_values": [kv.model_dump() for kv in body.key_values],
        "tables": [t.model_dump() for t in body.tables],
        "created_by": current_user["uid"],
        "created_at": now,
        "updated_at": now,
    }
    doc_ref = _templates_ref().document()
    doc_ref.set(data)
    return _to_response(doc_ref.id, data)


@router.post("/api/projects/{project_id}/apply-template/{template_id}", status_code=201)
async def apply_template(project_id: str, template_id: str, current_user: CurrentUser):
    """Apply a template to a project — creates all key-value and table assumptions."""
    doc = _templates_ref().document(template_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Template not found")

    template = doc.to_dict()
    db = get_firestore_client()
    prefix = settings.firestore_collection_prefix
    assumptions_ref = db.collection(f"{prefix}projects").document(project_id).collection("assumptions")
    now = datetime.now(UTC)

    created_count = 0

    # Create key-value assumptions
    for kv in template.get("key_values", []):
        doc_ref = assumptions_ref.document()
        doc_ref.set({
            "key": kv["key"],
            "display_name": kv.get("display_name", kv["key"]),
            "category": kv.get("category", "General"),
            "type": kv.get("type", "text"),
            "value": kv.get("default_value"),
            "format": "key_value",
            "columns": None,
            "source_id": None,
            "is_overridden": False,
            "version": 1,
            "created_at": now,
            "updated_at": now,
        })
        doc_ref.collection("history").add({
            "version": 1,
            "value": kv.get("default_value"),
            "previous_value": None,
            "changed_by": current_user["uid"],
            "changed_at": now,
            "reason": f"Template: {template.get('name', '')}",
        })
        created_count += 1

    # Create table assumptions
    for tbl in template.get("tables", []):
        doc_ref = assumptions_ref.document()
        columns = tbl.get("columns", [])
        doc_ref.set({
            "key": tbl["key"],
            "display_name": tbl.get("display_name", tbl["key"]),
            "category": tbl.get("category", "General"),
            "type": "text",
            "value": None,
            "format": "table",
            "columns": columns if isinstance(columns, list) else [c.model_dump() if hasattr(c, "model_dump") else c for c in columns],
            "source_id": None,
            "is_overridden": False,
            "version": 1,
            "created_at": now,
            "updated_at": now,
        })
        doc_ref.collection("history").add({
            "version": 1,
            "value": None,
            "previous_value": None,
            "changed_by": current_user["uid"],
            "changed_at": now,
            "reason": f"Template: {template.get('name', '')}",
        })
        created_count += 1

    return {"message": f"Template applied: {created_count} assumptions created", "count": created_count}


@router.post("/api/templates/seed", status_code=201)
async def seed_templates(current_user: CurrentUser):
    """Seed pre-built assumption templates. Idempotent — skips if templates exist."""
    ref = _templates_ref()
    existing = list(ref.limit(1).stream())
    if existing:
        return {"message": "Templates already seeded", "count": 0}

    now = datetime.now(UTC)
    templates = [
        {
            "name": "Multifamily Acquisition",
            "description": "Standard multifamily property acquisition model with rent roll and operating expenses.",
            "key_values": [
                {"key": "purchase_price", "display_name": "Purchase Price", "category": "Acquisition", "type": "currency", "default_value": None},
                {"key": "unit_count", "display_name": "Unit Count", "category": "Property", "type": "number", "default_value": None},
                {"key": "year_built", "display_name": "Year Built", "category": "Property", "type": "number", "default_value": None},
                {"key": "cap_rate", "display_name": "Cap Rate", "category": "Returns", "type": "percentage", "default_value": None},
                {"key": "vacancy_rate", "display_name": "Vacancy Rate", "category": "Revenue", "type": "percentage", "default_value": 0.05},
                {"key": "annual_rent_growth", "display_name": "Annual Rent Growth", "category": "Revenue", "type": "percentage", "default_value": 0.03},
                {"key": "loan_amount", "display_name": "Loan Amount", "category": "Financing", "type": "currency", "default_value": None},
                {"key": "interest_rate", "display_name": "Interest Rate", "category": "Financing", "type": "percentage", "default_value": None},
                {"key": "loan_term_years", "display_name": "Loan Term (years)", "category": "Financing", "type": "number", "default_value": 30},
            ],
            "tables": [
                {
                    "key": "rent_roll",
                    "display_name": "Rent Roll",
                    "category": "Revenue",
                    "columns": [
                        {"name": "unit", "type": "text"},
                        {"name": "type", "type": "text"},
                        {"name": "sqft", "type": "number"},
                        {"name": "market_rent", "type": "currency"},
                        {"name": "current_rent", "type": "currency"},
                        {"name": "lease_start", "type": "date"},
                        {"name": "lease_end", "type": "date"},
                    ],
                },
                {
                    "key": "operating_expenses",
                    "display_name": "Operating Expenses",
                    "category": "Expenses",
                    "columns": [
                        {"name": "category", "type": "text"},
                        {"name": "annual_amount", "type": "currency"},
                        {"name": "per_unit", "type": "currency"},
                        {"name": "notes", "type": "text"},
                    ],
                },
            ],
            "created_by": current_user["uid"],
            "created_at": now,
            "updated_at": now,
        },
        {
            "name": "Development Pro Forma",
            "description": "Ground-up development project with unit mix and development budget.",
            "key_values": [
                {"key": "land_cost", "display_name": "Land Cost", "category": "Acquisition", "type": "currency", "default_value": None},
                {"key": "total_units", "display_name": "Total Units", "category": "Property", "type": "number", "default_value": None},
                {"key": "total_sqft", "display_name": "Total Sqft", "category": "Property", "type": "number", "default_value": None},
                {"key": "construction_cost_psf", "display_name": "Construction Cost ($/sqft)", "category": "Construction", "type": "currency", "default_value": None},
                {"key": "construction_duration_months", "display_name": "Construction Duration (months)", "category": "Construction", "type": "number", "default_value": 18},
                {"key": "stabilization_months", "display_name": "Stabilization Period (months)", "category": "Revenue", "type": "number", "default_value": 6},
                {"key": "exit_cap_rate", "display_name": "Exit Cap Rate", "category": "Returns", "type": "percentage", "default_value": None},
            ],
            "tables": [
                {
                    "key": "unit_mix",
                    "display_name": "Unit Mix",
                    "category": "Property",
                    "columns": [
                        {"name": "type", "type": "text"},
                        {"name": "count", "type": "number"},
                        {"name": "avg_sqft", "type": "number"},
                        {"name": "target_rent", "type": "currency"},
                    ],
                },
                {
                    "key": "development_budget",
                    "display_name": "Development Budget",
                    "category": "Construction",
                    "columns": [
                        {"name": "line_item", "type": "text"},
                        {"name": "amount", "type": "currency"},
                        {"name": "pct_of_total", "type": "percentage"},
                        {"name": "notes", "type": "text"},
                    ],
                },
            ],
            "created_by": current_user["uid"],
            "created_at": now,
            "updated_at": now,
        },
    ]

    for t in templates:
        ref.document().set(t)

    return {"message": f"Seeded {len(templates)} templates", "count": len(templates)}
