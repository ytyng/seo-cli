"""Google Search Console API subcommands."""
from __future__ import annotations

from typing import Any

import click

from seo_cli.auth import catch_google_errors
from seo_cli.google_search_console.client import (
    build_service,
    flatten_search_analytics_row,
)
from seo_cli.output import FORMATS, emit
from seo_cli.settings import require_profile_value

GSC_API_MAX_ROW_LIMIT = 25000  # Per-request max (Google official limit)
SITE_URL_KEY = "google_search_console_site_url"

_format_option = click.option(
    "--format",
    "format_",
    type=click.Choice(list(FORMATS)),
    default="json",
    show_default=True,
)

_site_url_option = click.option(
    "--site-url",
    default=None,
    help=(
        "Site URL (`https://example.com/` or `sc-domain:example.com`). "
        f"Falls back to active profile's '{SITE_URL_KEY}'."
    ),
)


@click.group(name="google-search-console")
def google_search_console() -> None:
    """Google Search Console API wrapper.

    site_url format:
    - URL prefix: `https://www.example.com/` (trailing slash required)
    - Domain property: `sc-domain:example.com`
    """


@google_search_console.command("sites-list")
@_format_option
@catch_google_errors
def sites_list(format_: str) -> None:
    """List owned / accessible sites."""
    service = build_service()
    response = service.sites().list().execute()
    rows = response.get("siteEntry", [])
    emit(rows, format=format_)


@google_search_console.command("query")
@_site_url_option
@click.option("--start-date", required=True, help="YYYY-MM-DD")
@click.option("--end-date", required=True, help="YYYY-MM-DD")
@click.option(
    "--dimension",
    "dimensions",
    multiple=True,
    type=click.Choice(
        ["query", "page", "country", "device", "date", "searchAppearance"]
    ),
    help=(
        "Repeatable. Order determines the key order in results. "
        "NOTE: searchAppearance cannot be combined with other dimensions."
    ),
)
@click.option(
    "--row-limit",
    type=int,
    default=1000,
    show_default=True,
    help="Total rows to fetch. Values above 25,000 are paginated internally.",
)
@click.option("--start-row", type=int, default=0, show_default=True)
@click.option(
    "--search-type",
    type=click.Choice(
        ["web", "image", "video", "news", "discover", "googleNews"]
    ),
    help="Defaults to API default (web) if unspecified",
)
@click.option(
    "--data-state",
    type=click.Choice(["final", "all"]),
    default="final",
    show_default=True,
    help="'all' includes fresh (unstable) data",
)
@_format_option
@catch_google_errors
def query(
    site_url: str | None,
    start_date: str,
    end_date: str,
    dimensions: tuple[str, ...],
    row_limit: int,
    start_row: int,
    search_type: str | None,
    data_state: str,
    format_: str,
) -> None:
    """Search Analytics query (clicks / impressions / CTR / position).

    Data has a 2-3 day delay and covers up to 16 months.
    """
    resolved_site = require_profile_value(SITE_URL_KEY, site_url, "--site-url")
    service = build_service()

    remaining = row_limit
    current_row = start_row
    all_rows: list[dict[str, Any]] = []

    while remaining > 0:
        chunk = min(remaining, GSC_API_MAX_ROW_LIMIT)
        body: dict[str, Any] = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": list(dimensions),
            "rowLimit": chunk,
            "startRow": current_row,
            "dataState": data_state,
        }
        if search_type:
            body["searchType"] = search_type
        response = service.searchanalytics().query(
            siteUrl=resolved_site, body=body
        ).execute()

        rows = response.get("rows", [])
        if not rows:
            break
        all_rows.extend(flatten_search_analytics_row(r, dimensions) for r in rows)

        if len(rows) < chunk:
            break
        remaining -= len(rows)
        current_row += len(rows)

    emit(all_rows, format=format_)


@google_search_console.command("sitemaps-list")
@_site_url_option
@_format_option
@catch_google_errors
def sitemaps_list(site_url: str | None, format_: str) -> None:
    """List submitted sitemaps."""
    resolved_site = require_profile_value(SITE_URL_KEY, site_url, "--site-url")
    service = build_service()
    response = service.sitemaps().list(siteUrl=resolved_site).execute()
    rows = response.get("sitemap", [])
    emit(rows, format=format_)


@google_search_console.command("sitemaps-get")
@click.argument("feedpath")
@_site_url_option
@_format_option
@catch_google_errors
def sitemaps_get(feedpath: str, site_url: str | None, format_: str) -> None:
    """Show status of a specific sitemap."""
    resolved_site = require_profile_value(SITE_URL_KEY, site_url, "--site-url")
    service = build_service()
    response = service.sitemaps().get(
        siteUrl=resolved_site, feedpath=feedpath
    ).execute()
    emit(response, format=format_)


@google_search_console.command("sitemaps-submit")
@click.argument("feedpath")
@_site_url_option
@catch_google_errors
def sitemaps_submit(feedpath: str, site_url: str | None) -> None:
    """Submit a sitemap (write operation - requires writable scope)."""
    resolved_site = require_profile_value(SITE_URL_KEY, site_url, "--site-url")
    service = build_service(writable=True)
    service.sitemaps().submit(
        siteUrl=resolved_site, feedpath=feedpath
    ).execute()
    click.echo(f"submitted: {feedpath}")


@google_search_console.command("url-inspect")
@click.argument("url")
@_site_url_option
@click.option("--language-code", default="en-US", show_default=True)
@_format_option
@catch_google_errors
def url_inspect(
    url: str, site_url: str | None, language_code: str, format_: str
) -> None:
    """Inspect URL indexing status.

    Quota is strict (per property per day); be careful with bulk usage.
    """
    resolved_site = require_profile_value(SITE_URL_KEY, site_url, "--site-url")
    service = build_service()
    body: dict[str, Any] = {
        "inspectionUrl": url,
        "siteUrl": resolved_site,
        "languageCode": language_code,
    }
    response = service.urlInspection().index().inspect(body=body).execute()
    emit(response, format=format_)
