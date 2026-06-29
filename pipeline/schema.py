# financial_etl/schema.py
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
from typing import Optional

class TransactionSchema(BaseModel):
    """
    Validated transaction schema using Pydantic.
    """
    transaction_id: str = Field(..., min_length=64, max_length=64)
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    description: str = Field(..., min_length=1)
    amount: float = Field(...)
    source_file: str
    page: int = Field(ge=1)
    
    # Optional fields
    original_date: Optional[str] = None
    category: Optional[str] = None
    balance: Optional[float] = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v):
        if isinstance(v, (int, float, Decimal)):
            if abs(v) > 1_000_000_000:  # Sanity check
                raise ValueError("Amount is unrealistically large")
        return float(v)

    @field_validator("description")
    @classmethod
    def clean_description(cls, v):
        return str(v).strip()

    def to_dict(self):
        """Convert to dictionary for DataFrame / CSV export."""
        data = self.model_dump()
        # Remove None values for cleaner output
        return {k: v for k, v in data.items() if v is not None}


def create_transaction(data: dict) -> TransactionSchema:
    return TransactionSchema(**data)
