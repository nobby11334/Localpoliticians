# 公開資料による人物経歴の調査ツール（other-b）

公式名簿から本人の紹介・ホームページ・略歴・政策欄をたどり、確認経路と短い事実候補をJSONに記録する調査用ツールです。2026年11月5日に実施した調査の取得・追跡・監査・要約整理処理をまとめています。生HTML、取得キャッシュ、本文ダンプ、実行ログ、1,597人の入力・確定データは同梱していません。

取得結果は資料の記載です。現在の在職、役職の継続、政策の実現、実績との因果関係を保証するものではありません。候補者・過去の首長・現職は入力の区分を維持し、後任の経歴に置換しません。

## 動作環境

Python 3.10以上。

```sh
python -m pip install -r requirements.txt
```

外部依存はBeautiful Soupのみです。HTTP、JSON、並列処理はPython標準ライブラリを使います。

## 取得・追跡・監査

実行するコードのディレクトリと、入力・出力・キャッシュの置き場は独立しています。

```sh
export RESEARCH_INPUT="${PWD}/inputs/other-b.json"
export RESEARCH_OUTPUT_DIR="${PWD}/research-output"
export RESEARCH_CACHE_DIR="${PWD}/private-research-cache"
# 未指定時は実行日のISO日付。実際に本文を確認した日を指定してください。
export RESEARCH_CHECKED_AT="$(date +%F)"

python research-other-b.py
python follow-hp-other-b.py
python audit-other-b.py
```

1. `research-other-b.py` は既存の公式出典・本人紹介URLを取得し、本人名を確認した範囲内の明示的な略歴・学歴・職歴等を抽出します。最大6ワーカー、同一ホスト2接続、再試行1回です。取得の成否・キャッシュ利用を各人物の `attempted` に記録します。
2. `follow-hp-other-b.py` は本人の紹介欄で明示されたHPリンクと、本人サイト内のプロフィール・政策メニューを追加追跡します。リンク探索にナビゲーションを使っても、事実の抽出は取得先の本人範囲に限定します。
3. `audit-other-b.py` は取得済みキャッシュだけを再解析します。入力ID全件の対応、本人名境界、共有候補者カード、出典・確認日、私的事項、長文、第三者記述、重複などを点検します。追加のネットワーク取得は行いません。

各段階の出力は調査候補です。共有ページのテンプレート変更、引用された第三者、本人の活動記事と略歴の混在などは、公開前に原資料と照合してください。取得失敗・根拠未確認も削除せず残します。`既存内容確認` は出典の本人範囲を確認した意味で、既存の全記録を独立に再検証した意味ではありません。

### 入力形式

`RESEARCH_INPUT` はJSON配列です。`id` は全件で一意、自治体コードは5桁、`sourceNames` は確認済みの表記揺れだけを指定します。

```json
[
  {
    "id": "municipality-person-id",
    "municipalityCode": "13100",
    "name": "調査対象者名",
    "sourceNames": ["公式資料の確認済み表記"],
    "website": {"url": "https://example.invalid/profile", "kind": "公式プロフィール"},
    "sourceURL": "https://example.invalid/official-roster",
    "sources": [{"url": "https://example.invalid/official-roster"}],
    "findings": []
  }
]
```

`website` はURL文字列でも指定できます。既存 `findings` は同じ記載を再追加しないための照合に使います。出力は `{id, municipalityCode, name, findings, website?, enrichment}` の配列で、追加事項に `{matchedName, sectionHeading, selector, rule}` の `evidence` を付けます。

### 設定

| 環境変数 | 用途・既定値 |
|---|---|
| `RESEARCH_INPUT` | 人物入力。既定は実行ディレクトリの `other-b.json` |
| `RESEARCH_OUTPUT_DIR` | 出力先。既定は実行ディレクトリの `research-output/` |
| `RESEARCH_CACHE_DIR` | 非公開キャッシュ。既定は出力先の `private-cache/` |
| `RESEARCH_RESULT` | 結果JSON。既定は出力先の `enriched-other-b.json` |
| `RESEARCH_PARTIAL` | 途中結果。既定は出力先の `enriched-other-b.partial.json` |
| `RESEARCH_AUDIT` | 監査JSON。既定は出力先の `audit-other-b.json` |
| `RESEARCH_CHECKED_AT` | 実際の確認日、`YYYY-MM-DD`。既定は実行日 |
| `RESEARCH_MAX_WORKERS` | 取得ワーカー数、1～6。既定6 |
| `RESEARCH_HOST_CONCURRENCY` | 同一ホスト同時取得数、1～2。既定2 |
| `RESEARCH_HTTP_TIMEOUT` | 通信タイムアウト秒。既定12、正数 |
| `RESEARCH_LEGACY_DIR` | 任意。旧 `expanded` 相当のデータ・キャッシュを明示的に再利用する場合のみ指定 |

既存キャッシュは再利用されます。再取得する場合は新しいキャッシュディレクトリを指定してください。キャッシュ確認日は出典の更新日とは区別されます。キャッシュには原資料の私的情報も含まれ得るため、生成物と分離し公開対象に含めないでください。

## 2026年11月5日版の要約整理

`curate-policy-other-b.py` と `curate-quality-other-b.py` は、当時確認した特定人物・特定記載に対応する要約・分類の補正です。将来のWebページや別の入力に無条件で適用する汎用処理ではありません。

当時の入力・キャッシュを保有し、原資料との対応を確認してその版を再現する場合だけ、明示して実行できます。確認日を過去に戻して新しい取得結果を当時の資料として扱わないでください。

```sh
export RESEARCH_USE_SNAPSHOT_CURATIONS=1
export RESEARCH_CHECKED_AT=2026-11-05
python curate-policy-other-b.py
python curate-quality-other-b.py
```

新しい調査では取得・追跡・監査の出力をレビューし、要約ルールも必要に応じて更新してください。これらの補正スクリプトは、明示指定と日付が一致しなければ停止します。

## 首長30名の確認済み要約を再生成

`reviewed-mayors-2026-11-05.json` は、2025年4月30日名簿の30名についてWebで追加確認した153件の短い事実要約・URL・資料日・本人照合根拠です。原本文の複製は含みません。`mayors-targets-2025-04-30.json` は対応する自治体コード・氏名等の対象一覧です。

```sh
export RESEARCH_MAYORS_OUTPUT="${PWD}/research-output/enriched-mayors-web-followup.json"
python build-mayors-web-followup.py
```

この処理はネットワークを使いません。`RESEARCH_MAYORS_FACTS` で確認済み要約JSON、`RESEARCH_MAYORS_INPUT` で対象一覧JSON、`RESEARCH_MAYORS_OUTPUT` で出力ファイルを変更できます。既定の前二者は同梱JSON、既定の出力は `RESEARCH_OUTPUT_DIR` 配下です。

照合は自治体コード・氏名・`snapshotAsOf` で行います。要約がない人物は根拠未確認として残し、対象名簿日が異なれば停止します。再生成しても元の `checkedAt` は更新しません。新しい確認日は、新たに出典を読んで要約JSONを更新したときだけ付けてください。川口・松戸・町田の旧首長は後任のプロフィールと分離し、近藤弥生氏の別表記は出典上の氏名として保持しています。

## 公開範囲

公開用に同梱するのはPythonコード、依存一覧、本README、短い確認済み要約と対象一覧だけです。取得したHTML、PDF、CSV原本、キャッシュ、ログ、途中結果をリポジトリに追加しないでください。収録したURLの内容・利用条件・ページ構造は変更され得ます。
