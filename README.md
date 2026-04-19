# seo-cli

SEO research CLI that wraps the Google Analytics (GA4) and Google Search Console APIs.
Designed to be invoked from Claude Code for investigating a site's SEO posture.

## Requirements

- Python 3.12+
- uv (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Google Cloud SDK (`gcloud`) if using ADC or authorized_user credentials

## Setup

```bash
uv sync
```

## Configuration (profiles)

Credentials, the default GA property ID, and the default GSC site URL are grouped per
**profile**. The whole settings blob is supplied via the
`SEO_CLI_SETTINGS_TOML` or `SEO_CLI_SETTINGS_JSON` environment variable.

### TOML sample

JSON strings **must** be wrapped in a triple-quote literal (`'''...'''`) so that
newlines are preserved and backslashes (e.g. `\n` inside `private_key`) are not
interpreted.

```toml
default_profile = "ytyng"

[profiles.ytyng]
google_analytics_credentials_json = '''
{
  "type": "authorized_user",
  "client_id": "...",
  "client_secret": "...",
  "refresh_token": "..."
}
'''
google_analytics_property_id = "123456789"
google_search_console_credentials_json = '''
{
  "type": "authorized_user",
  "client_id": "...",
  "client_secret": "...",
  "refresh_token": "..."
}
'''
google_search_console_site_url = "https://www.ytyng.com/"

[profiles.cyberneura]
google_analytics_credentials_json = '''
{
  "type": "service_account",
  "project_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIE...\n-----END PRIVATE KEY-----\n",
  "client_email": "seo-cli@my-project.iam.gserviceaccount.com",
  "token_uri": "https://oauth2.googleapis.com/token"
}
'''
google_analytics_property_id = "987654321"
google_search_console_credentials_json = '''
{ ... same ... }
'''
google_search_console_site_url = "sc-domain:cyberneura.com"
```

### JSON sample (equivalent structure)

```json
{
  "default_profile": "ytyng",
  "profiles": {
    "ytyng": {
      "google_analytics_credentials_json": "{...}",
      "google_analytics_property_id": "123456789",
      "google_search_console_credentials_json": "{...}",
      "google_search_console_site_url": "https://www.ytyng.com/"
    }
  }
}
```

### Profile keys

| Key | Meaning |
|---|---|
| `google_analytics_credentials_json` | GA4 credentials JSON string |
| `google_analytics_property_id` | Default GA4 property ID (used when `--property-id` is omitted) |
| `google_search_console_credentials_json` | GSC credentials JSON string |
| `google_search_console_site_url` | Default GSC site URL (used when `--site-url` is omitted) |
| `credentials_json` | Shared fallback used for either service when the service-specific key is absent |

### TOML string literal cheatsheet

| Form | Newlines | Backslashes | JSON use |
|---|---|---|---|
| `"..."` | No | Interpreted | Breaks |
| `"""..."""` | Yes | Interpreted | Breaks |
| `'...'` | **No** | Literal | OK for single-line JSON |
| `'''...'''` | **Yes** | Literal | **Use this** |

### Credentials JSON format

The value stored in `credentials_json` is a Google credentials JSON string.
The `type` field is auto-detected:

- `"type": "service_account"` → service account JSON
- `"type": "authorized_user"` → the JSON produced by
  `gcloud auth application-default login` at
  `~/.config/gcloud/application_default_credentials.json`

The easiest way to obtain an `authorized_user` JSON is:

```bash
gcloud auth application-default login \
  --scopes="openid,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/analytics.readonly,https://www.googleapis.com/auth/webmasters.readonly"
cat ~/.config/gcloud/application_default_credentials.json
# → paste the output into the profile's credentials_json
```

### Profile resolution order

When `--profile <name>` is omitted:

1. `SEO_CLI_DEFAULT_PROFILE` environment variable
2. `default_profile` key in settings
3. If exactly one profile is defined, use it
4. Otherwise fall back to ADC (no profile)

### 1Password + `.loadenv.sh` workflow

Place a `.loadenv.sh` (gitignored) at the project root:

```bash
source load-env-from-1password --quiet seo-cli/.env
```

In 1Password, create an item `seo-cli/.env` with a field
`SEO_CLI_SETTINGS_TOML` containing the full TOML body.

Then:

```bash
source .loadenv.sh
uv run seo-cli google-analytics account-summaries
```

### Google-side permissions

#### Service account flow (recommended for teams / CI)

##### 1. Enable the APIs

```bash
gcloud services enable \
  analyticsdata.googleapis.com \
  analyticsadmin.googleapis.com \
  searchconsole.googleapis.com \
  --project=<PROJECT_ID>
```

##### 2. Create a service account

In the GCP console, IAM & Admin → Service Accounts → Create.

- Name: e.g. `seo-cli`
- **No project-level IAM role is required** (GA/GSC permissions are a separate system).
- Create a JSON key, download it, and save it in 1Password.
- The SA email has the form `seo-cli@<PROJECT_ID>.iam.gserviceaccount.com`.

##### 3. Grant GA4 access

In GA4, open the target property → Property access management → + → Add users.

- Email: the SA email
- Role: **Viewer** (seo-cli is read-only)

Repeat per property.

##### 4. Grant GSC access

In Search Console, open the target site → Settings → Users and permissions → Add user.

- Email: the SA email
- Permission:
  - **Restricted**: all read commands (`sites-list`, `query`, `sitemaps-list`, `sitemaps-get`, `url-inspect`)
  - **Full**: required for `sitemaps-submit`

Repeat per property. Note that URL-prefix and domain properties are separate.

#### authorized_user flow (personal account reuse — local dev)

If your own Google account already has GA/GSC access, skip the SA entirely:

```bash
gcloud auth application-default login \
  --scopes="openid,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/analytics.readonly,https://www.googleapis.com/auth/webmasters.readonly"
```

APIs still need to be enabled on a GCP project, but SA creation and property additions are unnecessary.

#### Summary

| Target | Permission needed |
|---|---|
| GCP project | Enable the three APIs. No IAM role needed on the SA. |
| GA4 property | Viewer or higher in Property access management |
| GSC property | Restricted or higher in Users and permissions (Full for `sitemaps-submit`) |

## Usage

```bash
# Profiles
uv run seo-cli profile list

# GA
uv run seo-cli google-analytics account-summaries
uv run seo-cli google-analytics run-report \
  --start-date 2026-04-01 --end-date 2026-04-18 \
  --dimension pagePath --dimension sessionSource \
  --metric sessions --metric organicGoogleSearchClicks \
  --format json
# Override the profile's property_id
uv run seo-cli google-analytics run-report --property-id 999999 \
  --start-date 2026-04-01 --end-date 2026-04-18 --metric sessions

# GSC
uv run seo-cli google-search-console sites-list
uv run seo-cli google-search-console query \
  --start-date 2026-04-01 --end-date 2026-04-18 \
  --dimension query --dimension page \
  --row-limit 1000 \
  --format tsv
uv run seo-cli google-search-console sitemaps-list
uv run seo-cli google-search-console sitemaps-get /sitemap.xml
uv run seo-cli google-search-console url-inspect https://www.example.com/foo

# Switch profile
uv run seo-cli --profile cyberneura google-analytics account-summaries
```

## Launcher script

`./seo-cli` at the project root is a zsh launcher that sources `.loadenv.sh` and
runs the CLI with a minimal-overhead `uv run`. After symlinking it onto your PATH,
`seo-cli ...` works from anywhere:

```bash
ln -s /Users/ytyng/workspace/seo-cli/seo-cli ~/home-files/bin/seo-cli
```

## Output formats

`--format` selects one of:

- `json` (default): structured output; best for LLM consumption
- `tsv`: tab-separated; best for `grep` / `awk` / scripts
- `human`: formatted table; best for human inspection

## References

- GA4 Data API: https://developers.google.com/analytics/devguides/reporting/data/v1
- Search Console API: https://developers.google.com/webmaster-tools
- Reference MCP implementation: https://github.com/googleanalytics/google-analytics-mcp
