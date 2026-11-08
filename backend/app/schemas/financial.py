"""Shared parsing for financial values entered in forms or sent through the API."""

import re
from decimal import Decimal
from typing import Any, get_args

from pydantic import BaseModel, ValidationInfo, field_validator

_GROUPED_DECIMAL = re.compile(r"[+-]?[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?")


class FinancialInputModel(BaseModel):
    """Accept US-style thousands grouping without changing decimal constraints."""

    @field_validator("*", mode="before")
    @classmethod
    def normalize_grouped_decimal(cls, value: Any, info: ValidationInfo) -> Any:
        annotation = cls.model_fields[info.field_name].annotation
        if annotation is not Decimal and Decimal not in get_args(annotation):
            return value
        if not isinstance(value, str) or "," not in value:
            return value
        text = value.strip()
        if not _GROUPED_DECIMAL.fullmatch(text):
            raise ValueError("Use thousands groups of three digits, for example 12,234.56")
        return text.replace(",", "")
