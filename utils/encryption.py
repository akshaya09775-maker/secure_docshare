"""
Encryption helpers for documents at rest.

Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256 for authenticity)
from the `cryptography` library. Every file written to disk is encrypted;
plaintext bytes only ever exist in memory, during an authorized request.
"""
from cryptography.fernet import Fernet


def get_fernet(key: str) -> Fernet:
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_bytes(data: bytes, key: str) -> bytes:
    f = get_fernet(key)
    return f.encrypt(data)


def decrypt_bytes(token: bytes, key: str) -> bytes:
    f = get_fernet(key)
    return f.decrypt(token)
