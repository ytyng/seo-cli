---
name: test-seo-cli
description: seo-cli の動作検証を段階的に実行する手順。「seo-cli をテスト」「seo-cli の動作確認」「seo-cli が動くか確認」と言及された時に使用。
allowed-tools: Bash(./seo-cli:*), Bash(seo-cli:*)
---

# test-seo-cli

`seo-cli` の動作を段階的に検証する手順。
認証不要なテスト (Level 0-1) → 実 API を叩くテスト (Level 2+) の順で実行し、
どこまで通るかで問題切り分けを行う。

## 前提

- 実行ディレクトリ: `/Users/ytyng/workspace/seo-cli`
- ランチャー: `./seo-cli` (PATH に入っていれば `seo-cli`)
- 1Password desktop app が起動中であること (`.loadenv.sh` が `op read` を呼ぶため)

## 実行方法

各 Level のコマンドを順に流して、失敗した Level で原因切り分け。
成功判定はコメントに書いてある期待出力と照らし合わせて判断。

---

## Level 0: CLI 構造 (認証不要)

```bash
./seo-cli --version
# 期待: "seo-cli, version 0.1.0"

./seo-cli --help
# 期待: Commands に google-analytics / google-search-console / profile が並ぶ

./seo-cli profile --help
./seo-cli google-analytics --help
./seo-cli google-search-console --help
# 期待: それぞれサブコマンド一覧が表示される
```

**失敗した場合**: `uv sync` 忘れ、インストール不備、Python バージョン不一致などの可能性。
`cd /Users/ytyng/workspace/seo-cli && uv sync` を実行。

---

## Level 1: プロファイル解決 (認証不要)

```bash
./seo-cli profile list --format human
```

**期待出力の形**:

```
name   ga_property_id  gsc_site_url           has_ga_credentials  has_gsc_credentials
-----  --------------  ---------------------  ------------------  -------------------
ytyng  123456789       https://www.xxx.com/   True                True
```

**チェック項目**:
- 少なくとも 1 つ profile が出ているか
- `has_ga_credentials` / `has_gsc_credentials` が `True` か
- `ga_property_id` / `gsc_site_url` が設定されているか

**空 `[]` になる場合**:
- `.loadenv.sh` が失敗している (1Password desktop app が起動していない、op read 失敗で空文字上書き等)
- `source .loadenv.sh` を単独で流して確認:

```bash
cd /Users/ytyng/workspace/seo-cli
source .loadenv.sh
echo "${SEO_CLI_SETTINGS_TOML:0:100}"
# 期待: TOML の先頭 100 文字が表示される
```

- 何も出ない場合は 1Password app を起動するか、`op signin` を実行。

---

## Level 2: 認証経路 (実 API、軽量)

アクセス可能なリソース一覧を取る。クォータ消費が少なく、認証経路の確認に最適。

```bash
./seo-cli google-analytics account-summaries --format human
```

**期待**: GA4 のアカウント / プロパティ階層が表示される (profile の credentials で accessible な範囲)

```bash
./seo-cli google-search-console sites-list --format human
```

**期待**: GSC の所有 / 閲覧可能サイト一覧。`permissionLevel` が `siteOwner` / `siteFullUser` / `siteRestrictedUser` のいずれか。

**失敗パターン**:

| 症状 | 原因 |
|---|---|
| `PERMISSION_DENIED` / `403` | 対象プロパティに認証アカウントが追加されていない。GA4 or GSC 側で SA email / ユーザーを追加 |
| `The caller does not have permission` | GCP プロジェクトで該当 API が Enable されていない |
| `invalid_grant` | refresh_token 失効 / 期限切れ |
| `Access blocked: this app is blocked` | OAuth client の同意画面未完了 |

---

## Level 3: Data API (実 API、小量クエリ)

実際のレポート取得。**クォータ消費があるので limit / row-limit を小さく**。

### GA4 run-report

```bash
./seo-cli google-analytics run-report \
  --start-date 7daysAgo --end-date today \
  --metric sessions \
  --limit 5 \
  --format json
```

**期待出力**:
```json
{
  "row_count": <整数>,
  "dimension_headers": [],
  "metric_headers": [{"name": "sessions", "type": "TYPE_INTEGER"}],
  "rows": [{"sessions": "<数値>"}]
}
```

### GA4 run-realtime-report

```bash
./seo-cli google-analytics run-realtime-report \
  --metric activeUsers \
  --limit 5 \
  --format json
```

**期待**: `rows` に `activeUsers` が入る。0 人なら空行の可能性あり。

### GA4 get-metadata

```bash
./seo-cli google-analytics get-metadata --format json | head -30
```

**期待**: `dimensions` / `metrics` 配列が含まれる巨大 JSON の先頭。

### GSC query (非ディメンション)

```bash
./seo-cli google-search-console query \
  --start-date 7daysAgo --end-date today \
  --row-limit 5 \
  --format json
```

**期待**: 5 行以内の rows (dimension 未指定なので集計値 1 行になる)。

### GSC query (ディメンション指定)

```bash
./seo-cli google-search-console query \
  --start-date 7daysAgo --end-date today \
  --dimension query \
  --row-limit 5 \
  --format json
```

**期待**: 上位 5 クエリ。`query`, `clicks`, `impressions`, `ctr`, `position` フィールドを持つ。

---

## Level 4: マルチプロファイル

複数 profile を定義している環境のみ。

```bash
# 1. 明示切替
./seo-cli --profile <other_profile> google-analytics account-summaries --format human

# 2. 存在しない profile 名
./seo-cli --profile nonexistent google-analytics account-summaries 2>&1 | grep -E "profile.*が見つかりません"
# 期待: エラー "profile 'nonexistent' が見つかりません。定義済み: ..."

# 3. default profile 上書き
SEO_CLI_DEFAULT_PROFILE=<other_profile> ./seo-cli profile list --format json | head -5
```

---

## Level 5: 出力フォーマット切替

```bash
# tsv: タブ区切り
./seo-cli google-search-console query \
  --start-date 7daysAgo --end-date today \
  --dimension query --row-limit 3 \
  --format tsv

# 期待: ヘッダー行 + 3 行。カラムはタブで区切られる

# human: テーブル
./seo-cli google-search-console query \
  --start-date 7daysAgo --end-date today \
  --dimension query --row-limit 3 \
  --format human

# 期待: ヘッダー + ダッシュ罫線 + 行
```

---

## Level 6: オプション上書き

profile の値を CLI 引数で上書きできることを確認。

```bash
# --property-id 明示
./seo-cli google-analytics property-details \
  --property-id <some_property_id> \
  --format json

# --site-url 明示
./seo-cli google-search-console sitemaps-list \
  --site-url https://www.example.com/ \
  --format human
```

**期待**: 指定したリソースの情報が返る (profile default は無視される)。

---

## Level 7: ページング動作 (GSC)

GSC の 25,000 行チャンクを跨ぐケース。

```bash
./seo-cli google-search-console query \
  --start-date 28daysAgo --end-date today \
  --dimension query --dimension page \
  --row-limit 30000 \
  --format json | jq 'length'
```

**期待**: 30000 以下の数値 (大規模サイトなら 30000 近い)。API 側の 25K 上限を越えてちゃんと返ってくれば OK。

> ⚠️ 大規模サイトでないと 25K 超えを引き起こせない。小規模サイトでは Level 7 はスキップ可。

---

## 書き込み系テスト (デフォルトは実行しない)

以下はサイトマップを実際に送信するので、**明示的に指示された時のみ**実行:

```bash
# sitemaps-submit (書き込み系 — 慎重に)
./seo-cli google-search-console sitemaps-submit /sitemap.xml
```

**期待**: `submitted: /sitemap.xml` と出力。

`url-inspect` も本番 API だがクォータ厳しめなので控えめに:

```bash
./seo-cli google-search-console url-inspect https://www.example.com/some-page
```

---

## 判定サマリ

- **Level 0-1 通る** → CLI の構造・設定読み込みは OK。認証周りを疑う
- **Level 0-2 通る** → 認証 + 基本 API アクセスは OK。個別コマンドの問題を疑う
- **Level 3 以降で特定コマンドだけ失敗** → 権限 / クォータ / API 有効化を確認

## レポート形式

検証結果は以下の形式で報告:

```
Level 0 (構造): ✅ 全て通過
Level 1 (プロファイル): ✅ 1 profile 検出、両サービス credentials あり
Level 2 (認証): ✅ GA4 アカウント 2 件、GSC サイト 3 件アクセス可
Level 3 (Data API):
  - GA4 run-report: ✅
  - GA4 run-realtime-report: ✅
  - GSC query: ✅
Level 4 (マルチプロファイル): スキップ (profile 1 件のみ)
Level 5 (フォーマット): ✅
Level 6 (オプション上書き): ✅
```

失敗があれば失敗 Level の 1 つ手前までを通過と報告し、エラーメッセージを添えて原因を切り分ける。
