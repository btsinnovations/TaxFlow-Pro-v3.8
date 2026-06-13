"""
Export format endpoints.
"""

from fastapi import APIRouter
from typing import List
from api_models import ExportFormatOut

router = APIRouter()


@router.get("/formats", response_model=List[ExportFormatOut])
async def list_formats():
    return [
        ExportFormatOut(format="QIF", extension=".qif", available=True, description="HomeBank / Quicken Interchange Format"),
        ExportFormatOut(format="CSV", extension=".csv", available=True, description="Comma-separated values with headers"),
        ExportFormatOut(format="Excel", extension=".xlsx", available=False, description="Microsoft Excel (coming in v3.7)"),
        ExportFormatOut(format="OFX", extension=".ofx", available=False, description="Open Financial Exchange for QuickBooks"),
        ExportFormatOut(format="JSON", extension=".json", available=True, description="Machine-readable JSON export"),
        ExportFormatOut(format="PDF Summary", extension=".pdf", available=False, description="Formatted PDF report with charts"),
    ]
