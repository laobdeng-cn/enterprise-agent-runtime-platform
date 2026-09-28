from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    raw_password = "correct-horse-battery-staple"
    password_hash = hash_password(raw_password)

    assert password_hash != raw_password
    assert verify_password(raw_password, password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_access_token_roundtrip() -> None:
    token = create_access_token(
        "00000000-0000-0000-0000-000000000001",
        "test-user",
    )

    payload = decode_access_token(token)

    assert payload["sub"] == "00000000-0000-0000-0000-000000000001"
    assert payload["username"] == "test-user"
    assert payload["type"] == "access"
