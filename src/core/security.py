import hashlib
import secrets


def hash_password(password: str, salt: str | None = None) -> str:
    actual_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        actual_salt.encode("utf-8"),
        120_000,
    )
    return f"{actual_salt}${digest.hex()}"


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        salt, expected = hashed_password.split("$", 1)
    except ValueError:
        return False
    return hash_password(password, salt).split("$", 1)[1] == expected

