"""Unit tests for Fernet encryption helpers."""

from perfsage.core.ai._crypto import decrypt_key, encrypt_key


def test_encrypt_decrypt_roundtrip() -> None:
    secret = "test-secret-key-32bytes-padded!!"
    plaintext = "sk-test-api-key-12345"
    encrypted = encrypt_key(plaintext, secret)
    assert encrypted != plaintext
    decrypted = decrypt_key(encrypted, secret)
    assert decrypted == plaintext


def test_different_secrets_give_different_ciphertext() -> None:
    ct1 = encrypt_key("key", "secret1")
    ct2 = encrypt_key("key", "secret2")
    assert ct1 != ct2


def test_encrypted_value_is_string() -> None:
    encrypted = encrypt_key("my-api-key", "any-secret")
    assert isinstance(encrypted, str)
    assert len(encrypted) > 0


def test_decrypt_wrong_secret_raises() -> None:
    import pytest
    from cryptography.fernet import InvalidToken

    encrypted = encrypt_key("api-key", "correct-secret")
    with pytest.raises(InvalidToken):
        decrypt_key(encrypted, "wrong-secret")
