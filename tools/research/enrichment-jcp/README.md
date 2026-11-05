# 日本共産党掲載議員の公開情報調査

党の個人紹介から、氏名・自治体が一致する略歴と、明示されたHPのプロフィール・政策を取得します。Python 3.10以上。入力データ・調査結果・原HTML・キャッシュ・ログは同梱していません。

```bash
python -m pip install -r requirements.txt
export JCP_INPUT=/path/to/input.json
export JCP_OUTPUT=/path/to/results/enriched.json
export JCP_CACHE_DIR=/path/to/private-cache/jcp
export JCP_CHECKED_AT=2026-11-05
python enrich_jcp.py --max-new=300
# CHECKPOINTなら同じコマンドで再開。全入力IDが揃った時に完成JSONを出力。
python retry_audit_jcp.py
```

入力はJSON配列。各行に `id`, `municipalityCode`, `name`, `municipalityName`, `prefecture` が必要です。`website` は党個人紹介のURL文字列、または `{ "url": "..." }`。党個人紹介がない場合は既存HPや `sourceURL` / `sources[].url` を調べます。`sourceNames` は確認済みの別名、`findings` は既存事実の照合に任意で使用します。別人・別名の推測統合は行いません。

出力は入力全IDの配列です。追加事実には出典・区画・一致氏名を、各人には取得履歴と確認状況を記録します。資料の掲載日、キャッシュの取得日、今回の確認日は区別します。取得失敗・追加根拠未確認は「経歴なし」を意味しません。

| 環境変数 | 既定値 / 用途 |
|---|---|
| `JCP_INPUT` | 実行ディレクトリの `jcp-input.json` |
| `JCP_OUTPUT` | 実行ディレクトリの `enriched-jcp.json` |
| `JCP_CACHE_DIR` | 実行ディレクトリの `.cache/jcp` |
| `JCP_CHECKED_AT` | 実行日のISO日付 |
| `JCP_REPORT` | 出力名に `-report.json` を付加 |
| `JCP_PROGRESS` | 出力名の拡張子を `.progress.jsonl` に変更 |
| `JCP_RETRY_OUTPUT` | 出力名に `-retry.json` を付加 |
| `JCP_MAX_NEW` | 1回の未処理人数上限。未指定は全員。CLIの `--max-new=N` 優先 |
| `JCP_REPARSE` | `1` でチェックポイントを退避して再解析（`--reparse` と同じ） |
| `JCP_REFRESH` | `1` でキャッシュ利用を止めて再取得。`JCP_REPARSE=1` と併用 |
| `JCP_WORKERS` / `JCP_PER_HOST` | 全体8以下 / 同一host4以下。既定値8 / 4 |
| `JCP_TIMEOUT_SECONDS` | 20秒 |
| `JCP_RETRIES` | 1回。0または1のみ |
| `JCP_CLIENT_MAX_AGE_SECONDS` | 90秒で接続クライアントを更新 |
| `JCP_PROXY` | 未指定なら `HTTPS_PROXY` を使用。通常の実行環境に従う |

`retry_audit_jcp.py --audit-only` は通信せず、既存出力とキャッシュを使って再監査し、出力・報告を更新します。通常実行は一時的な接続失敗等だけを再試行します。同じ入力と確認日を指定してください。

住所・電話・生年月日・家族事項を追加事実にせず、共有ページの汎用本文や議員団の共同政策・実績を個人へ帰属させない監査を行います。抽出は規則ベースなので、公開前には出典と `evidence` を確認してください。実行時に生成するキャッシュには元ページが含まれるため、公開リポジトリには入れないでください。
