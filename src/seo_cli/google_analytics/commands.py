"""GA4 (Google Analytics Data / Admin API) subcommands."""
from __future__ import annotations

from typing import Any

import click
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunRealtimeReportRequest,
    RunReportRequest,
)

from seo_cli.auth import catch_google_errors
from seo_cli.google_analytics.client import (
    build_admin_client,
    build_data_client,
    property_resource,
    proto_to_dict,
)
from seo_cli.output import FORMATS, emit
from seo_cli.settings import require_profile_value

PROPERTY_ID_KEY = "google_analytics_property_id"

_format_option = click.option(
    "--format",
    "format_",
    type=click.Choice(list(FORMATS)),
    default="json",
    show_default=True,
)

_property_id_option = click.option(
    "--property-id",
    default=None,
    help=(
        "GA4 property ID. Falls back to active profile's "
        f"'{PROPERTY_ID_KEY}'. The `properties/` prefix is optional."
    ),
)


@click.group(name="google-analytics")
def google_analytics() -> None:
    """Google Analytics (GA4) Data / Admin API wrapper.

    --property-id accepts both `123456789` and `properties/123456789`.
    """


@google_analytics.command("account-summaries")
@_format_option
@catch_google_errors
def account_summaries(format_: str) -> None:
    """List accessible accounts and properties hierarchically."""
    client = build_admin_client()
    summaries = []
    for summary in client.list_account_summaries():
        summaries.append(
            {
                "account": summary.account,
                "display_name": summary.display_name,
                "properties": [
                    {
                        "property": p.property,
                        "display_name": p.display_name,
                        "parent": p.parent,
                        "property_type": p.property_type.name,
                    }
                    for p in summary.property_summaries
                ],
            }
        )
    emit(summaries, format=format_)


@google_analytics.command("property-details")
@_property_id_option
@_format_option
@catch_google_errors
def property_details(property_id: str | None, format_: str) -> None:
    """Show property details (currency, timezone, data retention, etc.)."""
    resolved = require_profile_value(PROPERTY_ID_KEY, property_id, "--property-id")
    client = build_admin_client()
    prop = client.get_property(name=property_resource(resolved))
    emit(proto_to_dict(prop), format=format_)


@google_analytics.command("get-metadata")
@_property_id_option
@_format_option
@catch_google_errors
def get_metadata(property_id: str | None, format_: str) -> None:
    """List available dimensions / metrics for the property."""
    resolved = require_profile_value(PROPERTY_ID_KEY, property_id, "--property-id")
    client = build_data_client()
    metadata = client.get_metadata(name=f"{property_resource(resolved)}/metadata")
    emit(proto_to_dict(metadata), format=format_)


@google_analytics.command("run-report")
@_property_id_option
@click.option("--start-date", required=True, help="YYYY-MM-DD or NdaysAgo")
@click.option("--end-date", required=True, help="YYYY-MM-DD or today")
@click.option("--dimension", "dimensions", multiple=True, help="Repeatable")
@click.option(
    "--metric", "metrics", multiple=True, required=True, help="Repeatable"
)
@click.option(
    "--limit",
    type=int,
    default=10000,
    show_default=True,
    help="Max rows (GA4 per-request cap is 250,000)",
)
@click.option(
    "--offset",
    type=int,
    default=0,
    show_default=True,
    help="Paging start offset",
)
@_format_option
@catch_google_errors
def run_report(
    property_id: str | None,
    start_date: str,
    end_date: str,
    dimensions: tuple[str, ...],
    metrics: tuple[str, ...],
    limit: int,
    offset: int,
    format_: str,
) -> None:
    """GA4 Data API runReport."""
    resolved = require_profile_value(PROPERTY_ID_KEY, property_id, "--property-id")
    client = build_data_client()
    request = RunReportRequest(
        property=property_resource(resolved),
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[Dimension(name=d) for d in dimensions],
        metrics=[Metric(name=m) for m in metrics],
        limit=limit,
        offset=offset,
    )
    response = client.run_report(request=request)
    emit(_render_report(response, format_), format=format_)


@google_analytics.command("run-realtime-report")
@_property_id_option
@click.option("--dimension", "dimensions", multiple=True, help="Repeatable")
@click.option(
    "--metric", "metrics", multiple=True, required=True, help="Repeatable"
)
@click.option("--limit", type=int, default=10000, show_default=True)
@_format_option
@catch_google_errors
def run_realtime_report(
    property_id: str | None,
    dimensions: tuple[str, ...],
    metrics: tuple[str, ...],
    limit: int,
    format_: str,
) -> None:
    """Realtime report for the last 30 minutes."""
    resolved = require_profile_value(PROPERTY_ID_KEY, property_id, "--property-id")
    client = build_data_client()
    request = RunRealtimeReportRequest(
        property=property_resource(resolved),
        dimensions=[Dimension(name=d) for d in dimensions],
        metrics=[Metric(name=m) for m in metrics],
        limit=limit,
    )
    response = client.run_realtime_report(request=request)
    emit(_render_report(response, format_), format=format_)


@google_analytics.command("list-google-ads-links")
@_property_id_option
@_format_option
@catch_google_errors
def list_google_ads_links(property_id: str | None, format_: str) -> None:
    """List Google Ads links for the property."""
    resolved = require_profile_value(PROPERTY_ID_KEY, property_id, "--property-id")
    client = build_admin_client()
    links = [
        proto_to_dict(link)
        for link in client.list_google_ads_links(parent=property_resource(resolved))
    ]
    emit(links, format=format_)


def _render_report(response: Any, format_: str) -> Any:
    """Convert RunReportResponse / RunRealtimeReportResponse to output-ready shape."""
    dim_names = [h.name for h in response.dimension_headers]
    metric_headers = [
        {"name": h.name, "type": h.type_.name} for h in response.metric_headers
    ]
    metric_names = [h["name"] for h in metric_headers]

    rows: list[dict[str, Any]] = []
    for r in response.rows:
        row: dict[str, Any] = {}
        for i, name in enumerate(dim_names):
            row[name] = r.dimension_values[i].value
        for i, name in enumerate(metric_names):
            row[name] = r.metric_values[i].value
        rows.append(row)

    if format_ == "json":
        return {
            "row_count": getattr(response, "row_count", len(rows)),
            "dimension_headers": dim_names,
            "metric_headers": metric_headers,
            "rows": rows,
        }
    return rows
