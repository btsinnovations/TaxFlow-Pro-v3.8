"""Layout-family parsers for bank and credit-card statements.

These parsers are format-aware but institution-agnostic. They are selected by
the institution registry when no dedicated parser exists for a specific bank.
"""

from .csv_standard import CsvStandardFamily
from .ofx_qfx import OfxQfxFamily
from .pdf_table_simple import PdfTableSimpleFamily
from .pdf_table_multi import PdfTableMultiFamily
from .credit_card_pdf import CreditCardPdfFamily
from .brokerage_pdf import BrokeragePdfFamily

__all__ = [
    "CsvStandardFamily",
    "OfxQfxFamily",
    "PdfTableSimpleFamily",
    "PdfTableMultiFamily",
    "CreditCardPdfFamily",
    "BrokeragePdfFamily",
]
