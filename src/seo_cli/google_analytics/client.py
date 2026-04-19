"""Thin wrapper around the GA4 Admin / Data API clients."""
from __future__ import annotations

from typing import Any

from google.analytics.admin_v1beta import AnalyticsAdminServiceClient
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.protobuf.json_format import MessageToDict

from seo_cli.auth import ANALYTICS_READONLY_SCOPE, get_credentials

SERVICE = "google_analytics"


def build_admin_client() -> AnalyticsAdminServiceClient:
    credentials = get_credentials(SERVICE, scopes=[ANALYTICS_READONLY_SCOPE])
    return AnalyticsAdminServiceClient(credentials=credentials)


def build_data_client() -> BetaAnalyticsDataClient:
    credentials = get_credentials(SERVICE, scopes=[ANALYTICS_READONLY_SCOPE])
    return BetaAnalyticsDataClient(credentials=credentials)


def property_resource(property_id: str) -> str:
    """Accept both `123456789` and `properties/123456789`, returning the canonical form."""
    if property_id.startswith("properties/"):
        return property_id
    return f"properties/{property_id}"


def proto_to_dict(message: Any) -> dict[str, Any]:
    """Convert a proto / proto-plus message into a plain dict."""
    pb = message._pb if hasattr(message, "_pb") else message
    return MessageToDict(pb, preserving_proto_field_name=True)
