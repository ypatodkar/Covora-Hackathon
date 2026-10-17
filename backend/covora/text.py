import re
from typing import Any

# Stray punctuation that structured decoding sometimes leaves at the start of strings (".Operations Manager").
_LEADING_JUNK = re.compile(r"^[\s.:;,\-–—•*·]+")


def clean_text(value: str) -> str:
    return _LEADING_JUNK.sub("", value).strip()


def clean_strings(value: Any) -> Any:
    """Clean every string in a JSON-like value; drop strings that end up empty from lists."""
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, list):
        cleaned = [clean_strings(v) for v in value]
        return [v for v in cleaned if not (isinstance(v, str) and v == "")]
    if isinstance(value, dict):
        return {k: clean_strings(v) for k, v in value.items()}
    return value
