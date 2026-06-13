import yaml
from pathlib import Path
from typing import Dict, List, Optional

class CategoryLoader:
    _instance = None
    _categories: Dict = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _get_yaml_path(self) -> Path:
        # Try project root first (parent of the package directory)
        project_root = Path(__file__).parent.parent
        candidate = project_root / "categories.yaml"
        if candidate.exists():
            return candidate
        # Fallback: inside package (for backward compatibility)
        return Path(__file__).parent / "categories.yaml"

    def _load(self):
        path = self._get_yaml_path()
        if not path.exists():
            # No file: empty categories
            self._categories = {}
            return
        with open(path, "r", encoding="utf-8") as f:
            self._categories = yaml.safe_load(f) or {}

    def get_categories(self, profile: str = "personal") -> Dict[str, List[str]]:
        return self._categories.get(profile, {})

    def classify(self, description: str, profile: str = "personal") -> Optional[str]:
        categories = self.get_categories(profile)
        desc_lower = description.lower()
        for cat, keywords in categories.items():
            for kw in keywords:
                if kw in desc_lower:
                    return cat
        return None
