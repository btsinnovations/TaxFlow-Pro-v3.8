"""Tests for weak entropy audit (TASK-038-Entropy-Audit)."""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

from backend.local.security_random import (
    secure_alphanumeric,
    secure_random_int,
    secure_token,
    secure_urlsafe_token,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

SECURITY_MODULES = [
    Path("backend/auth.py"),
    Path("backend/local/auth.py"),
    Path("backend/local/crypto.py"),
    Path("backend/local/keyring_secret.py"),
    Path("backend/local/sqlcipher_engine.py"),
    Path("backend/routers/auth.py"),
]


def _ast_for(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def test_security_modules_do_not_import_random() -> None:
    """Security-critical modules must never import stdlib random."""
    for path in SECURITY_MODULES:
        if not path.exists():
            continue
        tree = _ast_for(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "random", f"{path} imports random"
            if isinstance(node, ast.ImportFrom) and node.module == "random":
                raise AssertionError(f"{path} imports from random")


def test_security_modules_use_secrets_for_tokens_keys_nonces() -> None:
    """Security-critical modules must use secrets.token_* for tokens/keys/nonces/salts."""
    for path in SECURITY_MODULES:
        if not path.exists():
            continue
        tree = _ast_for(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "random", f"{path} imports random"
            if isinstance(node, ast.ImportFrom):
                assert node.module != "random", f"{path} imports from random"


def test_no_insecure_random_callables_in_security_code() -> None:
    """AST scan: no random.randint/choice/shuffle/sample/seed in security modules."""
    insecure_names = {"randint", "choice", "shuffle", "sample", "seed", "random"}
    for path in SECURITY_MODULES:
        if not path.exists():
            continue
        tree = _ast_for(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "random":
                    assert node.func.attr not in insecure_names, (
                        f"{path} uses insecure random.{node.func.attr}()"
                    )


def test_secure_token_is_hex_and_reproduces_length() -> None:
    """secure_token(32) returns a 64-character hex string."""
    token = secure_token()
    assert len(token) == 64
    int(token, 16)  # must be valid hex


def test_secure_urlsafe_token_is_urlsafe() -> None:
    """secure_urlsafe_token returns only URL-safe base64 characters."""
    token = secure_urlsafe_token()
    assert set(token).issubset(set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._"))


def test_secure_random_int_within_range() -> None:
    """100 draws of secure_random_int stay within the requested inclusive range."""
    for _ in range(100):
        value = secure_random_int(10, 20)
        assert 10 <= value <= 20


def test_secure_random_int_rejects_invalid_range() -> None:
    """secure_random_int raises ValueError when min >= max."""
    with pytest.raises(ValueError):
        secure_random_int(20, 10)


def test_secure_alphanumeric_length_and_charset() -> None:
    """secure_alphanumeric returns an alphanumeric string of the requested length."""
    value = secure_alphanumeric(length=32)
    assert len(value) == 32
    assert value.isalnum()


def test_security_random_uses_secrets_not_random() -> None:
    """The security_random module itself must rely on secrets, not random."""
    spec = importlib.util.find_spec("backend.local.security_random")
    assert spec and spec.origin
    source = Path(spec.origin).read_text(encoding="utf-8")
    assert "import secrets" in source
    assert "import random" not in source
    assert "from random" not in source
