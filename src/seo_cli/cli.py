"""seo-cli entry point.

Subcommands:
- seo-cli profile ...                  Profile management
- seo-cli google-analytics ...         GA4 API wrapper
- seo-cli google-search-console ...    GSC API wrapper
"""
from __future__ import annotations

import click

from seo_cli import __version__
from seo_cli.google_analytics.commands import google_analytics
from seo_cli.google_search_console.commands import google_search_console
from seo_cli.profile.commands import profile


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="seo-cli")
@click.option(
    "--profile",
    "profile_",
    default=None,
    metavar="NAME",
    help=(
        "Profile name (defined in SEO_CLI_SETTINGS_TOML / _JSON). "
        "Resolved in order: SEO_CLI_DEFAULT_PROFILE env → settings.default_profile → "
        "single profile → ADC fallback."
    ),
)
@click.pass_context
def cli(ctx: click.Context, profile_: str | None) -> None:
    """SEO analysis CLI. Wrapper for Google Analytics (GA4) and Google Search Console APIs."""
    ctx.ensure_object(dict)
    ctx.obj["profile"] = profile_


cli.add_command(profile)
cli.add_command(google_analytics)
cli.add_command(google_search_console)
