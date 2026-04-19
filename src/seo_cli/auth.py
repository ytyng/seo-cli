"""Google API authentication helper with profile support.

Resolution order:
1. If --profile is set (or a default profile resolves), build credentials from the
   profile's service-specific `<service>_credentials_json`.
2. If the service-specific key is missing, fall back to the profile's shared
   `credentials_json`.
3. If neither is present, fall back to ADC (gcloud auth application-default login
   / GOOGLE_APPLICATION_CREDENTIALS / GCE/GKE metadata server).

The value of `credentials_json` is a raw Google credentials JSON string.
The `type` field selects between service_account and authorized_user.
"""
from __future__ import annotations

import json
from functools import wraps
from typing import Any, Callable, Literal, TypeVar

import click
import google.auth
from google.api_core.exceptions import GoogleAPICallError
from google.auth.credentials import Credentials
from google.auth.exceptions import (
    DefaultCredentialsError,
    GoogleAuthError,
)
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as OAuthUserCredentials
from googleapiclient.errors import HttpError

from seo_cli.settings import active_profile_name, get_profile

ANALYTICS_READONLY_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
SEARCH_CONSOLE_READONLY_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
SEARCH_CONSOLE_SCOPE = "https://www.googleapis.com/auth/webmasters"

Service = Literal["google_analytics", "google_search_console"]

_CREDENTIALS_KEY: dict[str, list[str]] = {
    "google_analytics": ["google_analytics_credentials_json", "credentials_json"],
    "google_search_console": [
        "google_search_console_credentials_json",
        "credentials_json",
    ],
}


def _credentials_from_info(info: dict[str, Any], scopes: list[str]) -> Credentials:
    cred_type = info.get("type")
    if cred_type == "service_account":
        return service_account.Credentials.from_service_account_info(
            info, scopes=scopes
        )
    if cred_type == "authorized_user":
        return OAuthUserCredentials.from_authorized_user_info(info, scopes=scopes)
    raise click.ClickException(
        f'Unsupported credentials JSON type="{cred_type}". '
        "Only service_account and authorized_user are supported."
    )


def _credentials_json_from_profile(
    profile: dict[str, Any], service: Service
) -> str | None:
    for key in _CREDENTIALS_KEY[service]:
        value = profile.get(key)
        if value:
            if not isinstance(value, str):
                raise click.ClickException(
                    f"profile key '{key}' must be a string"
                )
            return value
    return None


def get_credentials(
    service: Service,
    scopes: list[str],
    profile_name: str | None = None,
) -> Credentials:
    """Resolve credentials for the given service."""
    if profile_name is None:
        profile_name = active_profile_name()
    profile = get_profile(profile_name)

    if profile is not None:
        json_str = _credentials_json_from_profile(profile, service)
        if json_str:
            try:
                info = json.loads(json_str)
            except json.JSONDecodeError as e:
                key_hint = _CREDENTIALS_KEY[service][0]
                raise click.ClickException(
                    f"Failed to parse JSON in profile key '{key_hint}': {e}"
                ) from e
            return _credentials_from_info(info, scopes)

    # No profile, or no credentials for this service in the profile -> ADC fallback
    try:
        credentials, _project = google.auth.default(scopes=scopes)
    except DefaultCredentialsError as e:
        key_hint = _CREDENTIALS_KEY[service][0]
        profile_hint = (
            f" (profile={profile_name})" if profile_name else ""
        )
        raise click.ClickException(
            f"Google credentials not found{profile_hint}. Set one of:\n"
            f"  1) SEO_CLI_SETTINGS_TOML / _JSON with a profile that has '{key_hint}'\n"
            "  2) gcloud auth application-default login "
            '--scopes="https://www.googleapis.com/auth/analytics.readonly,'
            'https://www.googleapis.com/auth/webmasters.readonly"\n'
            "  3) export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json\n"
            f"Caused by: {e}"
        ) from e
    return credentials


F = TypeVar("F", bound=Callable[..., Any])


def catch_google_errors(func: F) -> F:
    """Decorator that converts common Google auth / API errors into ClickException.

    Covers:
    - GoogleAuthError subtree (RefreshError, TransportError, OAuthError, ...):
      credential refresh / OAuth / transport errors.
    - GoogleAPICallError subtree: gRPC-based API errors raised by
      `google-analytics-data` / `google-analytics-admin` (PermissionDenied,
      InvalidArgument, NotFound, ResourceExhausted, ...).
    - HttpError: REST API errors raised by `googleapiclient` (Search Console
      Discovery client).
    - PermissionError: filesystem error while loading SSL roots (e.g. sandboxed env).
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except GoogleAuthError as e:
            # RefreshError is the most common case (stale refresh token).
            # TransportError / OAuthError also land here.
            raise click.ClickException(
                "Google authentication error. The refresh token may be expired, "
                "or the network / OAuth server is unreachable. "
                "Re-authenticate with `gcloud auth application-default login` "
                "or replace the authorized_user JSON in your profile if this persists.\n"
                f"Caused by: {e}"
            ) from e
        except GoogleAPICallError as e:
            # gRPC-based API errors from GA4 Data / Admin clients.
            raise click.ClickException(f"Google API error: {e}") from e
        except HttpError as e:
            # REST-based API errors from GSC Discovery client.
            raise click.ClickException(f"Google API error: {e}") from e
        except PermissionError as e:
            raise click.ClickException(
                "Failed to initialize HTTPS (could not read SSL root certificates). "
                "Check filesystem permissions on Python's certifi bundle or the gRPC roots.pem.\n"
                f"Caused by: {e}"
            ) from e

    return wrapper  # type: ignore[return-value]
