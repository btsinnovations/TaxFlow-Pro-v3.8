"""Dedicated tests for local encryption primitives (TASK-038.13)."""
from __future__ import annotations

import pytest

from backend.local.crypto import (
    AuthenticationError,
    EncryptionError,
    LocalCryptoManager,
    generate_keyfile,
)


class TestAESGCM:
    def test_roundtrip_encrypt_decrypt(self):
        manager = LocalCryptoManager.create("master-password")
        plaintext = b"sensitive tax data"
        ciphertext = manager.encrypt(plaintext)
        assert manager.decrypt(ciphertext) == plaintext

    def test_tampered_ciphertext_raises_authentication_error(self):
        manager = LocalCryptoManager.create("master-password")
        ciphertext = manager.encrypt(b"secret data")
        # Tamper with a byte in the middle of the envelope bytes.
        tampered = ciphertext[: len(ciphertext) // 2] + b"X" + ciphertext[len(ciphertext) // 2 + 1 :]
        with pytest.raises((AuthenticationError, EncryptionError)):
            manager.decrypt(tampered)

    def test_wrong_associated_data_fails(self):
        manager = LocalCryptoManager.create("master-password")
        ciphertext = manager.encrypt(b"data", associated_data=b"context-a")
        with pytest.raises((AuthenticationError, EncryptionError)):
            manager.decrypt(ciphertext, associated_data=b"context-b")


class TestKeyfileFactor:
    def test_keyfile_factor_independence(self, tmp_path):
        keyfile = generate_keyfile(tmp_path / "test.key")

        password_only = LocalCryptoManager.create("same-password")
        with_keyfile = LocalCryptoManager.create("same-password", keyfile)

        ct_password_only = password_only.encrypt(b"password-only secret")
        ct_with_keyfile = with_keyfile.encrypt(b"keyfile-bound secret")

        # Keyfile-derived manager cannot decrypt password-only ciphertext.
        with pytest.raises((AuthenticationError, EncryptionError)):
            with_keyfile.decrypt(ct_password_only)

        # Password-only manager cannot decrypt keyfile-bound ciphertext.
        with pytest.raises((AuthenticationError, EncryptionError)):
            password_only.decrypt(ct_with_keyfile)

    def test_same_password_different_keyfiles_fail(self, tmp_path):
        keyfile_a = generate_keyfile(tmp_path / "a.key")
        keyfile_b = generate_keyfile(tmp_path / "b.key")

        manager_a = LocalCryptoManager.create("password", keyfile_a)
        manager_b = LocalCryptoManager.create("password", keyfile_b)

        ct = manager_a.encrypt(b"data")
        with pytest.raises((AuthenticationError, EncryptionError)):
            manager_b.decrypt(ct)


class TestSaltAndDerivation:
    def test_salt_uniqueness(self):
        manager_a = LocalCryptoManager.create("same-password")
        manager_b = LocalCryptoManager.create("same-password")
        assert manager_a._salt != manager_b._salt
        assert manager_a.salt_b64 != manager_b.salt_b64

    def test_from_stored_reproduces_same_key(self):
        original = LocalCryptoManager.create("password123")
        restored = LocalCryptoManager.from_stored("password123", original.salt_b64)
        ct = original.encrypt(b"roundtrip")
        assert restored.decrypt(ct) == b"roundtrip"

    def test_argon2_parameters_resist_weak_input(self):
        # Even a very short password must derive a valid 32-byte key.
        manager = LocalCryptoManager.create("a")
        assert len(manager._key) == 32
        ct = manager.encrypt(b"payload")
        assert manager.decrypt(ct) == b"payload"

    def test_invalid_salt_length_rejected(self):
        with pytest.raises(EncryptionError, match="Salt must be at least 16 bytes"):
            LocalCryptoManager.create("password", salt=b"tooshort")

    def test_invalid_key_length_rejected(self):
        with pytest.raises(EncryptionError, match="Encryption key must be 32 bytes"):
            LocalCryptoManager(b"tooshort", b"sixteen-byte-salt")


class TestEnvelope:
    def test_envelope_version_check(self):
        manager = LocalCryptoManager.create("pw")
        with pytest.raises(EncryptionError, match="Unsupported envelope version"):
            manager.decrypt(
                b'{"v": 999, "salt_b64": "", "nonce_b64": "", "ciphertext_b64": ""}'
            )

    def test_non_bytes_plaintext_rejected(self):
        manager = LocalCryptoManager.create("pw")
        with pytest.raises(TypeError, match="plaintext must be bytes"):
            manager.encrypt("not bytes")
