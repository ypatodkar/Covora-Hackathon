from covora.observability.redaction import redact


def test_redacts_secret_values_and_patterns():
    out = redact({"msg": "key nvapi-AAAA1111BBBB and Bearer ya29.tok", "list": ["s3cret"]}, ["s3cret"])
    assert "nvapi-" not in out["msg"] and "ya29." not in out["msg"] and out["list"] == ["[REDACTED]"]
