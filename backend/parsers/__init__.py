"""
Unified PDF parsing package for TaxFlow Pro v3.7+.

Provides:
- parse_pdf_to_dict()       API-compatible dict output (used by backend upload router).
- parse_pdf_to_transactions() List[Transaction] style dict output for CLI.
- detect_institution()      Institution detection shared with phase3 pipeline.
- dict_to_backend_model()   Convert parser dicts to backend DB insert kwargs.
- model_to_dict()             Convert backend DB rows to API-compatible dicts.
- deduplicate_dicts()         Deduplicate parsed transaction dicts.
- GenericPDFParser            Legacy backend statement parser class.
"""
from .generic_pdf import GenericPDFParser, parse_pdf_to_dict, parse_pdf_to_transactions, detect_institution
from .ocr_parser import OCRPDFParser, parse_pdf_to_cr_dict
from .institution import INSTITUTION_ALIASES, detect_institution_with_columns, parse_statement_pdf
from .transaction_builder import (
    dict_to_backend_model,
    model_to_dict,
    deduplicate_dicts,
    ensure_tx_type,
)
from .tdbank import TDBankParser, parse_td_bank_pdf
from .chime import ChimeParser, parse_chime_pdf
from .edfed import EdFedParser, parse_edfed_pdf
from .queensborough import QueensboroughParser, parse_queensborough_pdf
from .bankofamerica import BankOfAmericaParser, parse_bank_of_america_pdf
from .chase import ChaseParser, parse_chase_pdf
from .wellsfargo import WellsFargoParser, parse_wells_fargo_pdf
from .navyfederal import NavyFederalParser, parse_navy_federal_pdf
from .usbank import USBankParser, parse_us_bank_pdf
from .citibank import CitibankParser, parse_citibank_pdf
from .pnc import PNCBankParser, parse_pnc_pdf
from .ally import AllyBankParser, parse_ally_pdf
from .sofi import SoFiParser, parse_sofi_pdf
from .truist import TruistParser, parse_truist_pdf
from .becu import BECUParser, parse_becu_pdf
from .discover import DiscoverBankParser, parse_discover_pdf
from .marcus import MarcusParser, parse_marcus_pdf
from .cashapp import CashAppParser, parse_cashapp_pdf
from .amex import AmexParser, parse_amex_pdf
from .usaa import USAAParser, parse_usaa_pdf
from .penfed import PenFedParser, parse_penfed_pdf
from .alliant import AlliantParser, parse_alliant_pdf
from .synchrony import SynchronyBankParser, parse_synchrony_pdf
from .huntington import HuntingtonBankParser, parse_huntington_pdf
from .citizens import CitizensBankParser, parse_citizens_pdf
from .capitalone import CapitalOneParser, parse_capital_one_pdf
from .schwab import SchwabBankParser, parse_schwab_pdf

__all__ = [
    "GenericPDFParser",
    "OCRPDFParser",
    "TDBankParser",
    "ChimeParser",
    "EdFedParser",
    "QueensboroughParser",
    "BankOfAmericaParser",
    "ChaseParser",
    "WellsFargoParser",
    "NavyFederalParser",
    "USBankParser",
    "CitibankParser",
    "PNCBankParser",
    "AllyBankParser",
    "SoFiParser",
    "TruistParser",
    "BECUParser",
    "DiscoverBankParser",
    "MarcusParser",
    "CashAppParser",
    "AmexParser",
    "USAAParser",
    "PenFedParser",
    "AlliantParser",
    "SynchronyBankParser",
    "HuntingtonBankParser",
    "CitizensBankParser",
    "CapitalOneParser",
    "SchwabBankParser",
    "parse_pdf_to_dict",
    "parse_pdf_to_transactions",
    "parse_pdf_to_cr_dict",
    "parse_statement_pdf",
    "parse_td_bank_pdf",
    "parse_chime_pdf",
    "parse_edfed_pdf",
    "parse_queensborough_pdf",
    "parse_bank_of_america_pdf",
    "parse_chase_pdf",
    "parse_wells_fargo_pdf",
    "parse_navy_federal_pdf",
    "parse_us_bank_pdf",
    "parse_citibank_pdf",
    "parse_pnc_pdf",
    "parse_ally_pdf",
    "parse_sofi_pdf",
    "parse_truist_pdf",
    "parse_becu_pdf",
    "parse_discover_pdf",
    "parse_marcus_pdf",
    "parse_cashapp_pdf",
    "parse_amex_pdf",
    "parse_usaa_pdf",
    "parse_penfed_pdf",
    "parse_alliant_pdf",
    "parse_synchrony_pdf",
    "parse_huntington_pdf",
    "parse_citizens_pdf",
    "parse_capital_one_pdf",
    "parse_schwab_pdf",
    "detect_institution",
    "detect_institution_with_columns",
    "INSTITUTION_ALIASES",
    "dict_to_backend_model",
    "model_to_dict",
    "deduplicate_dicts",
    "ensure_tx_type",
]