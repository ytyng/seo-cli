"""Profile settings loader.

The whole settings blob (multiple profiles) is passed via an environment variable:

- SEO_CLI_SETTINGS_TOML: TOML string
- SEO_CLI_SETTINGS_JSON: JSON string (same structure)

Structure (TOML example):

    default_profile = "ytyng"    # optional

    [profiles.ytyng]
    google_analytics_credentials_json = '''{"type":"authorized_user",...}'''
    google_analytics_property_id = "123456789"
    google_search_console_credentials_json = '''{"type":"authorized_user",...}'''
    google_search_console_site_url = "https://www.ytyng.com/"

    [profiles.cyberneura]
    google_analytics_credentials_json = '''{"type":"service_account",...}'''
    google_analytics_property_id = "987654321"
    google_search_console_credentials_json = '''{"type":"service_account",...}'''
    google_search_console_site_url = "sc-domain:cyberneura.com"
"""
from __future__ import annotations

import json
import os
import tomllib
from typing import Any

import click

ENV_SETTINGS_TOML = "SEO_CLI_SETTINGS_TOML"
ENV_SETTINGS_JSON = "SEO_CLI_SETTINGS_JSON"
ENV_DEFAULT_PROFILE = "SEO_CLI_DEFAULT_PROFILE"


def load_settings() -> dict[str, Any]:
    """Load the settings dict from the environment. Return an empty dict if unset."""
    toml_str = os.environ.get(ENV_SETTINGS_TOML)
    json_str = os.environ.get(ENV_SETTINGS_JSON)

    if toml_str and json_str:
        raise click.ClickException(
            f"Both {ENV_SETTINGS_TOML} and {ENV_SETTINGS_JSON} are set. "
            "Specify only one."
        )
    if toml_str:
        try:
            return tomllib.loads(toml_str)
        except tomllib.TOMLDecodeError as e:
            raise click.ClickException(
                f"Failed to parse {ENV_SETTINGS_TOML}: {e}"
            ) from e
    if json_str:
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise click.ClickException(
                f"Failed to parse {ENV_SETTINGS_JSON}: {e}"
            ) from e
    return {}


def list_profiles() -> dict[str, dict[str, Any]]:
    """Return defined profiles as {name: profile_dict}."""
    settings = load_settings()
    profiles = settings.get("profiles") or {}
    if not isinstance(profiles, dict):
        raise click.ClickException("settings.profiles must be a table/object")
    return profiles


def _default_profile_name(settings: dict[str, Any]) -> str | None:
    env_value = os.environ.get(ENV_DEFAULT_PROFILE)
    if env_value:
        return env_value
    value = settings.get("default_profile")
    if isinstance(value, str) and value:
        return value
    return None


def get_profile(name: str | None) -> dict[str, Any] | None:
    """Look up a profile dict.

    If `name` is given, look it up (error when missing).
    If `name` is None, pick one in this order:
      1. SEO_CLI_DEFAULT_PROFILE env
      2. settings `default_profile` key
      3. The sole profile, if exactly one is defined
      4. Otherwise None (caller should fall back to ADC)
    """
    settings = load_settings()
    profiles = settings.get("profiles") or {}
    if not isinstance(profiles, dict):
        raise click.ClickException("settings.profiles must be a table/object")

    if name:
        if name not in profiles:
            available = ", ".join(sorted(profiles.keys())) or "(no profiles defined)"
            raise click.ClickException(
                f"Profile '{name}' not found. Defined profiles: {available}"
            )
        return profiles[name]

    # name not given
    default_name = _default_profile_name(settings)
    if default_name:
        if default_name not in profiles:
            raise click.ClickException(
                f"default_profile='{default_name}' does not exist in profiles"
            )
        return profiles[default_name]

    if len(profiles) == 1:
        return next(iter(profiles.values()))

    return None


def active_profile_name() -> str | None:
    """Return the --profile value from the current click context, if any."""
    try:
        ctx = click.get_current_context(silent=True)
    except RuntimeError:
        return None
    if ctx is None:
        return None
    obj = ctx.find_root().obj
    if not isinstance(obj, dict):
        return None
    return obj.get("profile")


def active_profile() -> dict[str, Any] | None:
    """Resolve the profile for the current invocation.

    Uses the root --profile option from click context, or the fallback chain
    defined in `get_profile`.
    """
    return get_profile(active_profile_name())


def profile_or_cli(
    profile: dict[str, Any] | None, profile_key: str, cli_value: str | None
) -> str | None:
    """Resolve a value from CLI argument (preferred) or profile, else None."""
    if cli_value:
        return cli_value
    if profile is None:
        return None
    value = profile.get(profile_key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise click.ClickException(
            f"profile key '{profile_key}' must be a string"
        )
    return value


def require_profile_value(
    profile_key: str, cli_value: str | None, cli_option_name: str
) -> str:
    """Resolve profile_key from CLI value or active profile; raise UsageError if missing."""
    value = profile_or_cli(active_profile(), profile_key, cli_value)
    if not value:
        raise click.UsageError(
            f"{cli_option_name} is required (or set '{profile_key}' in active profile)"
        )
    return value
