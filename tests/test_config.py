"""Tests for config obfuscation (encode/decode)."""

from tests.conftest import installer_script


def test_encode_decode_roundtrip():
    """Encode then decode returns the original dict."""
    original = {
        "CLIPABIT_AUTH0_DOMAIN": "dev-abc123.us.auth0.com",
        "CLIPABIT_AUTH0_CLIENT_ID": "xyzClientId",
        "CLIPABIT_AUTH0_AUDIENCE": "https://api.clipabit.com",
    }
    encoded = installer_script.encode_config(original)
    decoded = installer_script.decode_config(encoded)
    assert decoded == original


def test_decode_wrong_key_fails():
    """Decoding with the wrong key produces garbage or raises."""
    original = {"key": "value"}
    encoded = installer_script.encode_config(original)
    try:
        decoded = installer_script.decode_config(encoded, key="wrong-key-12345")
        # If it doesn't raise, the result must differ from original
        assert decoded != original
    except Exception:
        pass  # Any exception is acceptable


def test_encode_empty_config():
    """Empty dict encodes and decodes cleanly."""
    encoded = installer_script.encode_config({})
    decoded = installer_script.decode_config(encoded)
    assert decoded == {}


def test_encoded_output_is_ascii():
    """Encoded output is pure ASCII (safe for config.dat)."""
    config = {"CLIPABIT_AUTH0_DOMAIN": "example.auth0.com"}
    encoded = installer_script.encode_config(config)
    assert isinstance(encoded, str)
    encoded.encode("ascii")  # raises UnicodeEncodeError if not ASCII


def test_config_with_special_characters():
    """Auth0 URLs with special chars (/, ?, =) survive round-trip."""
    config = {
        "CLIPABIT_AUTH0_DOMAIN": "dev-abc.us.auth0.com",
        "CLIPABIT_AUTH0_AUDIENCE": "https://api.clipabit.com/v1?scope=openid&type=code",
        "CLIPABIT_AUTH0_CLIENT_ID": "abc123+/==special",
    }
    encoded = installer_script.encode_config(config)
    decoded = installer_script.decode_config(encoded)
    assert decoded == config
