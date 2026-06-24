import re
from pathlib import Path
from typing import Dict, Optional

from backend.local.yaml_safe import safe_load_yaml_file

from .logger import Logger

logger = Logger("profile_manager")

class ProfileManager:
    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = self._get_default_path()
        self.config_path = config_path
        self.profiles = {}
        self.institution_map = {}
        self.account_fallbacks = []
        self.default_profile = "personal"
        self._load()
        self._validate()

    def _get_default_path(self) -> Path:
        # Try project root first
        project_root = Path(__file__).parent.parent
        candidate = project_root / "profiles.yaml"
        if candidate.exists():
            return candidate
        # Fallback: inside package
        return Path(__file__).parent / "profiles.yaml"

    def _load(self):
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = safe_load_yaml_file(self.config_path) or {}
        self.profiles = data.get("profiles", {})
        self.institution_map = data.get("institution_map", {})
        self.account_fallbacks = data.get("account_fallbacks", [])
        self.default_profile = data.get("default", "personal")

    def _validate(self):
        if self.default_profile not in self.profiles:
            raise ValueError(f"Default profile '{self.default_profile}' missing")

    def resolve_profile(self, institution_name: str = None, filename: str = None) -> str:
        if institution_name:
            for key, profile in self.institution_map.items():
                if key.lower() in institution_name.lower():
                    return profile
        if filename:
            for entry in self.account_fallbacks:
                if entry["id"] in filename:
                    return entry["profile"]
        return self.default_profile

    def get_profile_config(self, profile: str) -> dict:
        return self.profiles.get(profile, {})

    def normalize_payee(self, payee: str, profile: str) -> str:
        if not payee:
            return payee
        config = self.get_profile_config(profile)
        aliases = config.get("payee_aliases", {})
        payee_lower = payee.lower()
        for alias, canonical in aliases.items():
            if alias.lower() in payee_lower:
                return canonical
        return payee

    def get_homebank_account(self, profile: str) -> str:
        return self.get_profile_config(profile).get("homebank_account", "Unknown")
