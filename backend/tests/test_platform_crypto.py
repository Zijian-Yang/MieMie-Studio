import base64
import os

import pytest

from app.services.platform_crypto import (
    PlatformSecretCipher,
    PlatformSecretError,
    build_platform_secret_cipher,
)


def encoded_key(byte: int = 7) -> str:
    return base64.urlsafe_b64encode(bytes([byte]) * 32).decode("ascii")


def test_aes_gcm_round_trip_is_randomized_and_versioned():
    cipher = PlatformSecretCipher(encoded_key())

    first = cipher.encrypt("https://hooks.example.test/private")
    second = cipher.encrypt("https://hooks.example.test/private")

    assert first.startswith("v1.")
    assert second.startswith("v1.")
    assert first != second
    assert cipher.decrypt(first) == "https://hooks.example.test/private"
    assert cipher.decrypt(second) == "https://hooks.example.test/private"
    assert "hooks.example" not in first


def test_cipher_rejects_missing_short_and_malformed_keys(monkeypatch):
    for value in (
        "",
        "not-base64",
        base64.urlsafe_b64encode(b"short").decode(),
        f" {encoded_key()} ",
        "/" * 43 + "=",
        "+" * 43 + "=",
        encoded_key() + "=",
    ):
        monkeypatch.setenv("MIEMIE_PLATFORM_ENCRYPTION_KEY", value)
        with pytest.raises(PlatformSecretError) as exc:
            build_platform_secret_cipher()
        assert str(exc.value) == "platform_encryption_key_invalid"
        if value:
            assert value not in str(exc.value)


def test_cipher_accepts_canonical_padded_and_unpadded_urlsafe_keys():
    padded = encoded_key(251)

    for value in (padded, padded.rstrip("=")):
        cipher = PlatformSecretCipher(value)
        assert cipher.decrypt(cipher.encrypt("value")) == "value"


def test_cipher_rejects_tampering_wrong_key_and_unknown_version():
    encrypted = PlatformSecretCipher(encoded_key(1)).encrypt("secret-value")

    for cipher_text, cipher in (
        (encrypted[:-2] + "AA", PlatformSecretCipher(encoded_key(1))),
        (encrypted, PlatformSecretCipher(encoded_key(2))),
        ("v2." + encrypted.split(".", 1)[1], PlatformSecretCipher(encoded_key(1))),
    ):
        with pytest.raises(PlatformSecretError) as exc:
            cipher.decrypt(cipher_text)
        assert str(exc.value) == "platform_secret_decryption_failed"
        assert "secret-value" not in str(exc.value)


def test_cipher_rejects_empty_plaintext_and_masks_without_disclosing_value():
    cipher = PlatformSecretCipher(encoded_key())

    with pytest.raises(PlatformSecretError, match="platform_secret_empty"):
        cipher.encrypt("")

    masked = cipher.mask("abcdefghijklmnop")
    assert masked == "abc***********op"
    assert "defghijklm" not in masked
    assert cipher.mask("") == ""


def test_build_cipher_uses_environment_without_mutating_it(monkeypatch):
    key = encoded_key(9)
    monkeypatch.setenv("MIEMIE_PLATFORM_ENCRYPTION_KEY", key)

    cipher = build_platform_secret_cipher()

    assert cipher.decrypt(cipher.encrypt("value")) == "value"
    assert os.environ["MIEMIE_PLATFORM_ENCRYPTION_KEY"] == key
