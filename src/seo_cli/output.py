"""Output formatters tailored for Claude Code consumption."""
from __future__ import annotations

import json
import sys
from typing import Any, Literal

FormatName = Literal["json", "tsv", "human"]
FORMATS: tuple[FormatName, ...] = ("json", "tsv", "human")


def emit(data: Any, format: str = "json") -> None:
    """Write `data` to stdout in the requested format.

    - json: structured output (default); best for LLM consumption.
    - tsv:  tab-separated rows; best for grep / awk / scripts. Requires list[dict].
    - human: formatted text; table for list[dict], indented key:value for dict.
    """
    if format == "json":
        _emit_json(data)
    elif format == "tsv":
        _emit_tsv(data)
    elif format == "human":
        _emit_human(data)
    else:
        raise ValueError(f"unknown format: {format}")


def _emit_json(data: Any) -> None:
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2, default=str)
    sys.stdout.write("\n")


def _emit_tsv(data: Any) -> None:
    rows = _as_rows(data)
    if not rows:
        return
    headers = list(rows[0].keys())
    sys.stdout.write("\t".join(headers) + "\n")
    for row in rows:
        sys.stdout.write(
            "\t".join(_scalar(row.get(h, "")) for h in headers) + "\n"
        )


def _emit_human(data: Any) -> None:
    """Table for list[dict]; indented key:value view for dict; JSON as last resort."""
    rows = _as_rows(data)
    if rows:
        _emit_human_table(rows)
        return
    if isinstance(data, dict):
        _emit_human_kv(data)
        return
    _emit_json(data)


def _emit_human_table(rows: list[dict[str, Any]]) -> None:
    headers = list(rows[0].keys())
    str_rows = [[_scalar(row.get(h, "")) for h in headers] for row in rows]
    widths = [
        max(len(h), *(len(r[i]) for r in str_rows)) for i, h in enumerate(headers)
    ]
    sys.stdout.write("  ".join(h.ljust(w) for h, w in zip(headers, widths)) + "\n")
    sys.stdout.write("  ".join("-" * w for w in widths) + "\n")
    for row in str_rows:
        sys.stdout.write("  ".join(c.ljust(w) for c, w in zip(row, widths)) + "\n")


def _emit_human_kv(data: dict[str, Any], indent: int = 0) -> None:
    """Render a dict as indented key:value lines. Recurses into nested structures."""
    prefix = "  " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            sys.stdout.write(f"{prefix}{key}:\n")
            _emit_human_kv(value, indent + 1)
        elif isinstance(value, list):
            if not value:
                sys.stdout.write(f"{prefix}{key}: []\n")
                continue
            sys.stdout.write(f"{prefix}{key}:\n")
            for item in value:
                if isinstance(item, dict):
                    _emit_human_kv(item, indent + 1)
                    sys.stdout.write(f"{prefix}  ---\n")
                else:
                    sys.stdout.write(f"{prefix}  - {_scalar(item)}\n")
        else:
            sys.stdout.write(f"{prefix}{key}: {_scalar(value)}\n")


def _as_rows(data: Any) -> list[dict]:
    """Return `data` as a non-empty list[dict], else []."""
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data
    return []


def _scalar(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\t", " ").replace("\n", " ")
