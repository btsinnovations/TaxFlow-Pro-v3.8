"""
Runtime feature flags for the Financial ETL Pipeline.
These flags control optional features and legacy compatibility.
"""

# Old watcher (watchdog) – deprecated in favor of the new watchdog.py.
# Set to False because the old watcher is disabled and will be removed.
WATCHER_AVAILABLE = False

# Enable/disable OCR processing for scanned PDFs (if ocr.py is available).
OCR_AVAILABLE = True   # Set to False if you don't have Tesseract installed

# Enable/disable tax rule processing (tax.py).
TAX_PROCESSING_ENABLED = True

# Debug mode – enables verbose logging and preserves intermediate files.
DEBUG_MODE = False

# Maximum number of transactions to process in a single batch (for memory limiting).
MAX_TRANSACTIONS_BATCH = 10000

# Flag to indicate if the pipeline is running in a CI/test environment.
TEST_ENVIRONMENT = False