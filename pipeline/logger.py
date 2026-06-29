import logging
from pathlib import Path
from datetime import datetime

from .config import LOGS_DIR


class Logger:
    """
    Central logger wrapper with backward compatibility.
    Supports:
      - warning / warn
      - info
      - error
      - debug
      - exception
    """

    _instances = {}

    def __new__(cls, name: str):
        if name not in cls._instances:
            instance = super().__new__(cls)
            instance._initialized = False
            cls._instances[name] = instance
        return cls._instances[name]

    def __init__(self, name: str):
        if getattr(self, "_initialized", False):
            return

        self.name = name
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger(f"financial_etl.{name}")
        self.logger.setLevel(logging.INFO)

        if not self.logger.handlers:
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
            )

            # Console
            console = logging.StreamHandler()
            console.setFormatter(formatter)
            self.logger.addHandler(console)

            # File
            today = datetime.now().date().isoformat()
            file_handler = logging.FileHandler(
                LOGS_DIR / f"{today}.log",
                encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

        self._initialized = True

    # -------------------------
    # Core methods
    # -------------------------
    def info(self, msg): self.logger.info(msg)
    def error(self, msg): self.logger.error(msg)
    def debug(self, msg): self.logger.debug(msg)
    def exception(self, msg): self.logger.exception(msg)

    # -------------------------
    # Compatibility layer (FIX)
    # -------------------------
    def warn(self, msg): self.logger.warning(msg)
    def warning(self, msg): self.logger.warning(msg)
