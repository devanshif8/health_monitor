"""Password hashing / verification unit tests."""

from app.services.auth import create_access_token, hash_password, verify_password


def test_hash_is_not_plaintext():
    h = hash_password("hunter2pw")
    assert h != "hunter2pw"
    assert h.startswith("$2")  # bcrypt marker


def test_verify_correct_password():
    h = hash_password("hunter2pw")
    assert verify_password("hunter2pw", h) is True


def test_verify_wrong_password():
    h = hash_password("hunter2pw")
    assert verify_password("WRONGpass", h) is False


def test_hash_is_salted_unique():
    assert hash_password("samepw123") != hash_password("samepw123")


def test_password_over_72_bytes_does_not_raise():
    # bcrypt has a hard 72-byte limit; the service truncates safely.
    long_pw = "a" * 200
    h = hash_password(long_pw)
    assert verify_password(long_pw, h) is True


def test_verify_against_garbage_hash_returns_false():
    assert verify_password("anything", "not-a-real-hash") is False


def test_access_token_is_a_jwt_string():
    import uuid

    token = create_access_token(uuid.uuid4())
    assert token.count(".") == 2  # header.payload.signature
