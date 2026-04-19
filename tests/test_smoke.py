"""Smoke tests exercising CLI parsing without touching any network.

These tests verify that the click command tree is well-formed and that
profile resolution / output formatting work end-to-end in-process.
"""
from __future__ import annotations

import json

import click
import pytest
from click.testing import CliRunner

from seo_cli.cli import cli


def test_version() -> None:
    result = CliRunner().invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "seo-cli, version" in result.output


def test_root_help_lists_subgroups() -> None:
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    for name in ("profile", "google-analytics", "google-search-console"):
        assert name in result.output


def test_all_subcommand_help() -> None:
    """Every leaf command's --help must parse and return exit 0."""
    commands = [
        ("profile", "list"),
        ("google-analytics", "account-summaries"),
        ("google-analytics", "property-details"),
        ("google-analytics", "get-metadata"),
        ("google-analytics", "run-report"),
        ("google-analytics", "run-realtime-report"),
        ("google-analytics", "list-google-ads-links"),
        ("google-search-console", "sites-list"),
        ("google-search-console", "query"),
        ("google-search-console", "sitemaps-list"),
        ("google-search-console", "sitemaps-get"),
        ("google-search-console", "sitemaps-submit"),
        ("google-search-console", "url-inspect"),
    ]
    runner = CliRunner()
    for group, cmd in commands:
        result = runner.invoke(cli, [group, cmd, "--help"])
        assert result.exit_code == 0, f"{group} {cmd} --help failed: {result.output}"


def test_profile_list_empty_when_no_settings(monkeypatch) -> None:
    monkeypatch.delenv("SEO_CLI_SETTINGS_TOML", raising=False)
    monkeypatch.delenv("SEO_CLI_SETTINGS_JSON", raising=False)
    result = CliRunner().invoke(cli, ["profile", "list", "--format", "json"])
    assert result.exit_code == 0
    assert json.loads(result.output) == []


def test_profile_list_with_toml(monkeypatch) -> None:
    monkeypatch.delenv("SEO_CLI_SETTINGS_JSON", raising=False)
    monkeypatch.setenv(
        "SEO_CLI_SETTINGS_TOML",
        """
[profiles.alpha]
google_analytics_property_id = "111"
google_search_console_site_url = "https://a.example.com/"

[profiles.beta]
google_analytics_property_id = "222"
credentials_json = "{}"
""",
    )
    result = CliRunner().invoke(cli, ["profile", "list", "--format", "json"])
    assert result.exit_code == 0
    rows = json.loads(result.output)
    names = [r["name"] for r in rows]
    assert names == ["alpha", "beta"]
    beta = next(r for r in rows if r["name"] == "beta")
    assert beta["has_ga_credentials"] is True
    assert beta["has_gsc_credentials"] is True


def test_unknown_profile_errors(monkeypatch) -> None:
    monkeypatch.setenv(
        "SEO_CLI_SETTINGS_TOML",
        '[profiles.existing]\ngoogle_analytics_property_id = "1"\n',
    )
    result = CliRunner().invoke(
        cli, ["--profile", "nope", "google-analytics", "account-summaries"]
    )
    assert result.exit_code != 0
    assert "Profile 'nope' not found" in result.output


def test_toml_and_json_conflict(monkeypatch) -> None:
    monkeypatch.setenv("SEO_CLI_SETTINGS_TOML", "default_profile = 'a'")
    monkeypatch.setenv("SEO_CLI_SETTINGS_JSON", "{}")
    result = CliRunner().invoke(cli, ["profile", "list"])
    assert result.exit_code != 0
    assert "Specify only one" in result.output


def test_missing_property_id_error(monkeypatch) -> None:
    monkeypatch.delenv("SEO_CLI_SETTINGS_TOML", raising=False)
    monkeypatch.delenv("SEO_CLI_SETTINGS_JSON", raising=False)
    result = CliRunner().invoke(
        cli, ["google-analytics", "property-details"]
    )
    assert result.exit_code != 0
    assert "--property-id is required" in result.output


def test_missing_site_url_error(monkeypatch) -> None:
    monkeypatch.delenv("SEO_CLI_SETTINGS_TOML", raising=False)
    monkeypatch.delenv("SEO_CLI_SETTINGS_JSON", raising=False)
    result = CliRunner().invoke(
        cli, ["google-search-console", "sitemaps-get", "/sitemap.xml"]
    )
    assert result.exit_code != 0
    assert "--site-url is required" in result.output


def test_catch_google_errors_wraps_api_call_error() -> None:
    """GA4 gRPC errors (GoogleAPICallError subtree) must be surfaced as ClickException."""
    from google.api_core.exceptions import PermissionDenied

    from seo_cli.auth import catch_google_errors

    @catch_google_errors
    def raises_ga4_error() -> None:
        raise PermissionDenied("test denial")

    with pytest.raises(click.ClickException) as exc_info:
        raises_ga4_error()
    assert "Google API error" in exc_info.value.message
    assert "test denial" in exc_info.value.message


def test_catch_google_errors_wraps_auth_error() -> None:
    """GoogleAuthError subtree (RefreshError, TransportError, ...) must be surfaced."""
    from google.auth.exceptions import RefreshError

    from seo_cli.auth import catch_google_errors

    @catch_google_errors
    def raises_refresh_error() -> None:
        raise RefreshError("stale token")

    with pytest.raises(click.ClickException) as exc_info:
        raises_refresh_error()
    assert "authentication error" in exc_info.value.message.lower()
    assert "stale token" in exc_info.value.message
