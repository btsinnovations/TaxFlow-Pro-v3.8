"""Bank statement parsers – plugin registry with priority."""
import importlib
import pkgutil
from typing import List

from .base import BaseParser

PARSER_REGISTRY: List[BaseParser] = []
_REGISTERED_CLASSES = set()

def register_parser(cls):
    """Decorator-safe singleton registration."""
    if cls not in _REGISTERED_CLASSES:
        PARSER_REGISTRY.append(cls())
        _REGISTERED_CLASSES.add(cls)
    return cls

def _load_plugins():
    """Explicit plugin loader (safe, deterministic)."""
    import phase3_pipeline.parsers as pkg
    for _, module_name, _ in pkgutil.iter_modules(pkg.__path__):
        if module_name != "base":
            importlib.import_module(f".{module_name}", package="phase3_pipeline.parsers")
    PARSER_REGISTRY.sort(key=lambda p: getattr(p, "priority", 0), reverse=True)

_load_plugins()

def get_parser(text: str) -> BaseParser:
    """Return highest-priority matching parser."""
    for parser in PARSER_REGISTRY:
        if parser.can_handle(text):
            return parser
    # Fallback (should never be reached because GenericParser is always registered)
    from .generic import GenericParser
    return GenericParser()