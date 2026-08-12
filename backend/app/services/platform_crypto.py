"""Authenticated encryption for platform-level operational credentials."""

from __future__ import annotations

import base64
import binascii
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


_VERSION = "v1"
_AAD = b"miemie-platform-secret:v1"
_NONCE_BYTES = 12


class PlatformSecretError(RuntimeError):
    """Stable secret handling error that never embeds sensitive values."""


def _decode_key(value: str) -> bytes:
    try:
        encoded = value.strip().encode("ascii")
        key = base64.b64decode(encoded, altchars=b"-_", validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
        raise PlatformSecretError("platform_encryption_key_invalid") from exc
    if len(key) != 32:
        raise PlatformSecretError("platform_encryption_key_invalid")
    return key


class PlatformSecretCipher:
    """AES-256-GCM envelope cipher with explicit version and associated data."""

    def __init__(self, encoded_key: str):
        self._cipher = AESGCM(_decode_key(encoded_key))

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            raise PlatformSecretError("platform_secret_empty")
        nonce = os.urandom(_NONCE_BYTES)
        ciphertext = self._cipher.encrypt(nonce, plaintext.encode("utf-8"), _AAD)
        payload = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii").rstrip("=")
        return f"{_VERSION}.{payload}"

    def decrypt(self, envelope: str) -> str:
        try:
            version, payload = envelope.split(".", 1)
            if version != _VERSION:
                raise ValueError("unsupported envelope version")
            padding = "=" * (-len(payload) % 4)
            raw = base64.b64decode(
                (payload + padding).encode("ascii"), altchars=b"-_", validate=True
            )
            if len(raw) <= _NONCE_BYTES:
                raise ValueError("invalid envelope")
            plaintext = self._cipher.decrypt(raw[:_NONCE_BYTES], raw[_NONCE_BYTES:], _AAD)
            return plaintext.decode("utf-8")
        except (ValueError, UnicodeError, binascii.Error, InvalidTag) as exc:
            raise PlatformSecretError("platform_secret_decryption_failed") from exc

    @staticmethod
    def mask(value: str) -> str:
        if not value:
            return ""
        if len(value) <= 5:
            return "*" * len(value)
        return f"{value[:3]}{'*' * (len(value) - 5)}{value[-2:]}"


def build_platform_secret_cipher() -> PlatformSecretCipher:
    value = os.getenv("MIEMIE_PLATFORM_ENCRYPTION_KEY", "")
    try:
        return PlatformSecretCipher(value)
    except PlatformSecretError as exc:
        raise PlatformSecretError("platform_encryption_key_invalid") from exc


__all__ = [
    "PlatformSecretCipher",
    "PlatformSecretError",
    "build_platform_secret_cipher",
]
