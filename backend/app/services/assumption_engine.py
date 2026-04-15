"""Assumption engine — validation and history tracking."""
from datetime import date

from fastapi import HTTPException

from backend.app.models.assumption import AssumptionType


def validate_assumption_value(assumption_type: AssumptionType, value: object) -> object:
    """Validate and coerce a value to match the declared assumption type.

    Percentages are stored as decimals (0.05 = 5%).
    """
    if value is None:
        return None

    match assumption_type:
        case AssumptionType.NUMBER | AssumptionType.CURRENCY:
            try:
                return float(value)
            except (ValueError, TypeError) as err:
                raise HTTPException(status_code=422, detail=f"Invalid {assumption_type.value}: {value}") from err

        case AssumptionType.PERCENTAGE:
            try:
                v = float(value)
            except (ValueError, TypeError) as err:
                raise HTTPException(status_code=422, detail=f"Invalid percentage: {value}") from err
            # If > 1, assume user passed 5 instead of 0.05
            if v > 1:
                v = v / 100
            return v

        case AssumptionType.DATE:
            if isinstance(value, date):
                return value.isoformat()
            if isinstance(value, str):
                try:
                    date.fromisoformat(value)
                    return value
                except ValueError as err:
                    raise HTTPException(status_code=422, detail=f"Invalid date: {value}") from err
            raise HTTPException(status_code=422, detail=f"Invalid date: {value}")

        case AssumptionType.BOOLEAN:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes")
            return bool(value)

        case AssumptionType.TEXT:
            return str(value)
