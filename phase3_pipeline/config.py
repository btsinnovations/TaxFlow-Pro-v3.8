import os
from pathlib import Path
from typing import List, Tuple

# Logs directory – prefer the user's local data directory so packaged installs
# (e.g. /opt/taxflow-pro on Linux) do not try to write into read-only install dirs.
_local_root = Path(os.environ.get("TAXFLOW_LOCAL_ROOT", Path.home() / ".local/share/TaxFlowPro"))
LOGS_DIR = _local_root / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# (keyword, category, schedule_line, deductible)
TAX_RULES: List[Tuple[str, str, str, bool]] = [
    ("fuel", "fuel_expense", "[Car and Truck Expenses (Line 9)]", True),
    ("gas", "fuel_expense", "[Car and Truck Expenses (Line 9)]", True),
    ("shell oil", "fuel_expense", "[Car and Truck Expenses (Line 9)]", True),
    ("shell", "fuel_expense", "[Car and Truck Expenses (Line 9)]", True),
    ("chevron", "fuel_expense", "[Car and Truck Expenses (Line 9)]", True),
    ("exxon", "fuel_expense", "[Car and Truck Expenses (Line 9)]", True),
    ("mobil", "fuel_expense", "[Car and Truck Expenses (Line 9)]", True),
    ("marathon", "fuel_expense", "[Car and Truck Expenses (Line 9)]", True),
    ("speedway", "fuel_expense", "[Car and Truck Expenses (Line 9)]", True),
    ("bp", "fuel_expense", "[Car and Truck Expenses (Line 9)]", True),
    ("office supplies", "office_expense", "[Office Expenses (Line 18)]", True),
    ("postage", "shipping_postage", "[Other Expenses (Line 27a)]", True),
    ("meal", "meals_entertainment", "[Meals and Entertainment (Line 24b)]", True),
    ("repair", "repairs_maintenance", "[Repairs and Maintenance (Line 21)]", True),
    ("software", "software_saas", "[Other Expenses (Line 27a)]", True),
    ("tax", "taxes_licenses", "[Taxes and Licenses (Line 23)]", True),
    ("utilities", "utilities", "[Utilities (Line 25)]", True),
]

DEFAULT_CASHBACK = "20.00"
SPLIT_PATTERNS = [
    (r"cash\s*back\s*\$?(\d+(\.\d{2})?)", 1),
    (r"withdrawal.*cash\s*back\s*\$?(\d+(\.\d{2})?)", 2),
    (r"atm.*cash\s*back\s*\$?(\d+(\.\d{2})?)", 3),
    (r"atm.*\$?(\d+(\.\d{2})?)\s*cash", 4),
]

# ========== V3.5.2 additions ==========
# OCR Configuration (supports GPU)
OCR_CONFIG = {
    "use_angle_cls": True,
    "lang": "en",
    "show_log": False,
    "use_gpu": False,                # set to True if NVIDIA GPU available
    "enable_mkldnn": True,
    "cpu_threads": 4,
    "det_db_thresh": 0.3,
    "det_db_box_thresh": 0.5,
    "rec_score_thresh": 0.5,
    "table_structure": True,
    "prefer_digital": True,
    "pdf_dpi": 200,
}

# Machine Learning categorizer
USE_ML = True
ML_CONFIDENCE_THRESHOLD = 0.7
ML_MODEL_PATH = "ml_model.pkl"

# Watchdog
WATCHDOG_INPUT_DIR = "/home/e14/Desktop/Bank_Statements"
WATCHDOG_OUTPUT_DIR = "/home/e14/Desktop/Processed"
WATCHDOG_OUTPUT_FORMAT = "qif"
