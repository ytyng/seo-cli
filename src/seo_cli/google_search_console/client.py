"""Thin wrapper around the Google Search Console Discovery client."""
from __future__ import annotations

from typing import Any

from googleapiclient.discovery import Resource, build

from seo_cli.auth import (
    SEARCH_CONSOLE_READONLY_SCOPE,
    SEARCH_CONSOLE_SCOPE,
    get_credentials,
)

SERVICE = "google_search_console"


def build_service(*, writable: bool = False) -> Resource:
    """Return a Search Console API (v1) Discovery client.

    writable=True: use the full scope (required for sitemaps-submit and similar
    write operations).
    writable=False (default): use the read-only scope.
    """
    scope = SEARCH_CONSOLE_SCOPE if writable else SEARCH_CONSOLE_READONLY_SCOPE
    credentials = get_credentials(SERVICE, scopes=[scope])
    return build("searchconsole", "v1", credentials=credentials, cache_discovery=False)


def flatten_search_analytics_row(
    row: dict[str, Any], dimensions: tuple[str, ...]
) -> dict[str, Any]:
    """Flatten a searchanalytics.query row so dimensions become named keys."""
    keys = row.get("keys", [])
    flat: dict[str, Any] = {}
    for i, dim in enumerate(dimensions):
        flat[dim] = keys[i] if i < len(keys) else None
    flat["clicks"] = row.get("clicks", 0)
    flat["impressions"] = row.get("impressions", 0)
    flat["ctr"] = row.get("ctr", 0.0)
    flat["position"] = row.get("position", 0.0)
    return flat
