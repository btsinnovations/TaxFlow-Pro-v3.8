"""
Priority-based transaction categorizer with merchant alias normalization.
Reads categories.yaml which contains merchant_aliases and rules.
"""
import re
import yaml
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

class PriorityCategorizer:
    def __init__(self, rules_file: str = "categories.yaml"):
        self.rules_file = Path(rules_file)
        self.rules: List[Dict[str, Any]] = []
        self.aliases: Dict[str, str] = {}
        self._compiled_aliases: List[Tuple[re.Pattern, str]] = []
        self.load_rules()

    def load_rules(self):
        if not self.rules_file.exists():
            raise FileNotFoundError(f"Rules file not found: {self.rules_file}")
        with open(self.rules_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        # Load merchant aliases
        self.aliases = data.get("merchant_aliases", {})
        self._compile_aliases()
        # Load and sort rules by priority (descending)
        self.rules = data.get("rules", [])
        self.rules.sort(key=lambda r: r.get("priority", 0), reverse=True)
        for rule in self.rules:
            pattern = rule.get("pattern", "")
            if pattern and pattern != ".*":
                try:
                    rule["_compiled"] = re.compile(pattern, re.IGNORECASE)
                except re.error as e:
                    print(f"Warning: Invalid regex '{pattern}' - {e}")
                    rule["_compiled"] = None
            else:
                rule["_compiled"] = None

    def _compile_aliases(self):
        """Pre-compile regex patterns for each alias key."""
        self._compiled_aliases = []
        for key, value in self.aliases.items():
            # Convert alias key to regex pattern
            escaped = re.escape(key)
            # Replace escaped '\*' with '.*' to match any sequence
            pattern_str = escaped.replace('\\*', '.*')
            try:
                # Match from the start of the description, ignoring case
                pattern = re.compile(f"^{pattern_str}", re.IGNORECASE)
                self._compiled_aliases.append((pattern, value))
            except re.error:
                print(f"Warning: Invalid alias pattern '{key}' -> {value}")

    def _apply_aliases(self, text: str) -> str:
        """Apply merchant aliases to normalize the description."""
        if not text:
            return text

        # Prefer a start-of-string alias match and truncate trailing store/location
        # identifiers so variants like "WAL-MART #123" collapse to "WALMART".
        best_match = None
        for pattern, replacement in self._compiled_aliases:
            m = pattern.match(text)
            if m:
                if best_match is None or m.end() > best_match[0].end():
                    best_match = (m, replacement)
        if best_match:
            return best_match[1]

        # Fallback: apply all substring aliases as before.
        result = text
        for pattern, replacement in self._compiled_aliases:
            result = pattern.sub(lambda m: replacement, result)
        return result

    def categorize(self, description: str, payee: str = "") -> str:
        """
        Determine category for a transaction.
        First applies merchant aliases to the description, then runs regex rules.
        """
        # Combine payee and description
        text = f"{payee} {description}".strip()
        if not text:
            text = description
        # Normalize using merchant aliases
        normalized = self._apply_aliases(text)
        # Apply rules (case-insensitive)
        for rule in self.rules:
            compiled = rule.get("_compiled")
            if compiled and compiled.search(normalized):
                return rule.get("category", "Other:Uncategorized")
        return "Other:Uncategorized"

    def categorize_transaction(self, txn) -> str:
        """Convenience method for Transaction object."""
        payee = getattr(txn, 'payee', '')
        desc = getattr(txn, 'description', '')
        return self.categorize(desc, payee)
