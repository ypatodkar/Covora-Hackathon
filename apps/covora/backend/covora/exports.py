"""CSV exports. Web-sourced text is escaped so a spreadsheet never runs it as a formula."""

import csv
import io
from collections.abc import Iterable, Sequence
from typing import Any

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value: Any) -> str:
    if value is None:
        return ""
    text = value if isinstance(value, str) else ", ".join(map(str, value)) if isinstance(value, list) else str(value)
    return f"'{text}" if text.startswith(_FORMULA_PREFIXES) else text


def to_csv(header: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    for row in rows:
        writer.writerow([csv_safe(v) for v in row])
    return buffer.getvalue()
