"""Profile management commands."""
from __future__ import annotations

import click

from seo_cli.output import FORMATS, emit
from seo_cli.settings import list_profiles

_format_option = click.option(
    "--format",
    "format_",
    type=click.Choice(list(FORMATS)),
    default="human",
    show_default=True,
)


@click.group(name="profile")
def profile() -> None:
    """Manage profiles defined in SEO_CLI_SETTINGS_TOML / _JSON."""


@profile.command("list")
@_format_option
def list_(format_: str) -> None:
    """List defined profiles."""
    profiles = list_profiles()
    rows = []
    for name, prof in sorted(profiles.items()):
        rows.append(
            {
                "name": name,
                "ga_property_id": prof.get("google_analytics_property_id") or "",
                "gsc_site_url": prof.get("google_search_console_site_url") or "",
                "has_ga_credentials": bool(
                    prof.get("google_analytics_credentials_json")
                    or prof.get("credentials_json")
                ),
                "has_gsc_credentials": bool(
                    prof.get("google_search_console_credentials_json")
                    or prof.get("credentials_json")
                ),
            }
        )
    emit(rows, format=format_)
