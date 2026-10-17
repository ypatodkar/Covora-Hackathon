import json
import re

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_OPEN, _CLOSE = "<think>", "</think>"


def strip_reasoning(text: str) -> str:
    """Remove model reasoning so it is never stored or shown (spec §15.5)."""
    out = _THINK_BLOCK.sub("", text)
    lower = out.lower()
    if _CLOSE in lower:
        # The opening tag was part of the prompt template: everything before the close is reasoning.
        out = out[lower.rfind(_CLOSE) + len(_CLOSE) :]
        lower = out.lower()
    if _OPEN in lower:
        # Unterminated reasoning: drop it and everything after.
        out = out[: lower.find(_OPEN)]
    return out.strip()


def _balanced_end(text: str, start: int) -> int | None:
    """Index of the bracket closing the one at `start`, respecting JSON strings."""
    depth, in_string, escaped = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:
                return i
    return None


def extract_json(text: str) -> str:
    """Return the first parseable top-level JSON object or array in a model reply."""
    cleaned = strip_reasoning(text)
    for start, ch in enumerate(cleaned):
        if ch not in "{[":
            continue
        end = _balanced_end(cleaned, start)
        if end is None:
            continue
        candidate = cleaned[start : end + 1]
        try:
            json.loads(candidate)
        except json.JSONDecodeError:
            continue
        return candidate
    raise ValueError("no JSON found")
