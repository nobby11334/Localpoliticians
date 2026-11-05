# 公開プロフィールの取得と監査

行政・議会・政党の出典と、そこから本人欄に限定して辿れる公開サイトを確認する研究用スクリプトです。人物の在職・当選・政策実現を自動認定するものではありません。

今回の確定結果は入力1,598人・出力1,598人です。情報追加247人（632件）、既存内容確認4人、追加根拠未確認1,336人、取得失敗11人。取得履歴のあるURLは重複除外で1,407件、本人サイト確認126人です。本文スコープ・氏名・出典URL・私的情報パターン等の監査は問題0件でした。確認日は2026-11-05です。

## ファイル

- `enrich_profiles.py`：取得、本人部分のリンク探索、略歴・政策項目の抽出。再開と再解析に対応。
- `audit_profiles.py`：通信せず、入力とのID対応と保存済み本文への根拠包含を検査。集計JSONを出力。
- `requirements.txt`：今回使用した主要依存のバージョン。

原HTML・本文入りキャッシュ・人物入力・出力・進捗ログは、この公開用フォルダに含みません。

## 実行

Python 3.11以降を想定しています。

```bash
python -m pip install -r requirements.txt

export POLITICIAN_RESEARCH_INPUT="/path/to/people.json"
export POLITICIAN_RESEARCH_OUTPUT="/path/to/enriched.json"
export POLITICIAN_RESEARCH_CACHE="/path/to/private-cache"
export POLITICIAN_RESEARCH_REFERENCE_DIR="/path/to/reference-people"
export POLITICIAN_RESEARCH_CHECKED_AT="2026-11-05"

python enrich_profiles.py --refresh
python audit_profiles.py --stamp
```

入力はJSON配列です。各要素に `id`、`name`、5桁の `municipalityCode` が必要です。起点として `website`（URL文字列または `{url: ...}`）、`sourceURL`、`sources[].url` を使用します。既存の `findings`、本人名の別表記 `sourceNames`、候補者資料の印 `candidate` も参照します。住所・連絡先等を入力に含める必要はありません。

参照ディレクトリのJSON配列、または `people` 配列を持つJSONから、比較対象となる人物名と同じ自治体の公式名簿URLを読みます。これは共有ページで別人の欄を避ける補助に用います。入力自身の人物名も必ず読みます。

通常実行は既存出力のIDを飛ばして再開し、取得済みキャッシュを再利用します。`--reparse` は全入力を再解析します。`--refresh` は再開済みIDも処理し直し、各URLをその実行で一度再取得します。`--reparse --cached-only` は保存本文だけを用いた解析確認用です。新規取得を行う `--refresh` と `--cached-only` は併用しないでください。

## 環境変数

| 変数 | 用途・既定値 |
| --- | --- |
| `POLITICIAN_RESEARCH_DIR` | 未指定の入出力名の基準ディレクトリ。既定はスクリプトの場所 |
| `POLITICIAN_RESEARCH_INPUT` | 入力JSON。既定は基準ディレクトリの `input.json` |
| `POLITICIAN_RESEARCH_OUTPUT` | 出力JSON。既定は基準ディレクトリの `enriched.json` |
| `POLITICIAN_RESEARCH_CACHE` | 本文キャッシュ。既定はOS一時ディレクトリの `civic-profile-cache` |
| `POLITICIAN_RESEARCH_REFERENCE_DIR` | 人物名・自治体出典の参照JSON。既定は入力JSONの親ディレクトリ |
| `POLITICIAN_RESEARCH_CHECKED_AT` | 確認日。既定は実行日。保存本文の過去の確認を再現する場合だけ過去日を指定 |
| `POLITICIAN_RESEARCH_WORKERS` | 全体並列数。既定8、上限8 |
| `POLITICIAN_RESEARCH_HOST_LIMIT` | 同一ホストの並列数。既定2、上限2 |
| `POLITICIAN_RESEARCH_PROXY` | HTTPプロキシURL。未指定時は `HTTPS_PROXY` を参照 |
| `POLITICIAN_RESEARCH_AUDIT` | 監査集計JSON。既定は出力の拡張子を `.audit.json` に置換したもの |

HTTPはワーカーごとの接続再利用を行い、失敗時の再試行は1回です。429応答は指定待機時間を上限15秒で待ちます。探索は起点最大4URLと深さ2までの個人向けリンクに限定し、1人あたり最大8URLです。

## 採用規則と限界

- 氏名の一致は、入力名と出典上の別表記を空白除去・NFKC正規化して確認します。無関係な別人のプロフィールへ進んでも、本人一致を確認できなければ採用しません。
- 共有選挙ページ・共有名簿の経歴本文は採用しません。本人を含む最小の欄から、本人サイト・個別プロフィールのリンクだけを探索します。
- 単独人物ページでも、明示的な略歴・職歴・プロフィール・政策等の範囲に限定します。引用欄、周辺ナビゲーション、別の既知人物名を含む文は除外します。
- 既存名簿の所属確認だけを新しい略歴として増やしません。新規事実を確認できない場合も全員を結果に残し、取得履歴と理由を記録します。
- 本人や政党が掲載した略歴は、その掲載内容として扱います。雇用主・学校・資格機関による独立の裏付けを意味しません。政策は掲載された分野・取り組みとして収録し、事業の実現や本人の寄与は認定しません。
- 年代・元職等は本文で確認できる範囲だけを残します。更新日が不明な `asOf` は不明のままで、`checkedAt` を在職・役職の現任確認日に転用しません。候補者掲載も現職の根拠に転用しません。
- 「追加根拠未確認」は情報が存在しないという意味ではありません。リンク非掲載、氏名表記差、JavaScript描画、接続失敗、探索上限、対応していない書式等で未収録となる場合があります。独立した氏名検索による全Web網羅調査ではありません。

`evidence` には照合した氏名、節の見出し、採用規則、取得URL、キャッシュキーを保存します。`cacheKey` はフラグメントを除いた取得URLのSHA-256です。`contentSha256` はキャッシュJSONの `data.text` をUTF-8にした本文のSHA-256です。元HTTPバイト列そのもののハッシュではありません。

監査は、記録された取得本文に対するルール検査です。世の中の事実の独立検証ではありません。本文キャッシュは監査の再現に必要ですが、公開ページ上の住所・電話等が含まれ得るため、公開リポジトリや配布物に同梱しないでください。出力JSONには、採用した短い要約と必要な出典情報だけを残します。
