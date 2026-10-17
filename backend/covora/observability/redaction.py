import re
from collections.abc import Sequence
from typing import Any

REDACTED = "[REDACTED]"

# NVIDIA keys, bearer tokens, Google access tokens, Google refresh tokens.
_PATTERNS = [
    re.compile(r"nvapi-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"ya29\.[A-Za-z0-9._\-]+"),
    re.compile(r"1//[A-Za-z0-9._\-]{20,}"),
]


def redact(value: Any, secrets: Sequence[str]) -> Any:
    """Replace secret values and token-shaped strings anywhere inside `value`."""
    if isinstance(value, str):
        out = value
        for secret in sorted((s for s in secrets if s), key=len, reverse=True):
            out = out.replace(secret, REDACTED)
        for pattern in _PATTERNS:
            out = pattern.sub(REDACTED, out)
        return out
    if isinstance(value, dict):
        return {k: redact(v, secrets) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [redact(v, secrets) for v in value]
    return value
