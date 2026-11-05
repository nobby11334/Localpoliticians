# 首長プロフィールの取得・監査・補足統合

全国首長名簿等の**固定された人物一覧**を入力し、自治体公式トップから首長紹介・プロフィールを追跡する調査用スクリプトです。名簿掲載者が現在の首長と異なる場合、後任の略歴を引き継ぎません。政治家の評価点や政策の達成度は生成しません。

Python 3.10以降。検証環境は aiohttp 3.14.4 / lxml 6.1.1。依存は `requirements.txt` に記載しています。

```sh
python -m pip install -r path/to/public-mayors/requirements.txt
export MAYORS_WORK_DIR="/path/to/private-work"
export MAYORS_NATIONAL_INPUT="/path/to/repository/data/national.json"
export MAYORS_CHECKED_AT="2026-11-05"
python path/to/public-mayors/prepare-input.py
python path/to/public-mayors/enrich-mayors.py
python path/to/public-mayors/finalize-mayors.py
```

作業先を指定しない場合、OSの一時ディレクトリ下 `localpoliticians-mayors` を使います。固定された環境固有の作業パスはありません。取得したHTML・中間JSON・チェックポイントを公開用ソースディレクトリへ保存しないでください。公開する結果は最終統合後の `MAYORS_OUTPUT` です。

## 入力と出力

`prepare-input.py` はリポジトリの `national.json` の `municipalities` 配列から入力を生成します。`code/name/pref/officialURL` と `mayor.name/asOf/sourceURL` を使います。作成済みの入力JSONがある場合は `MAYORS_INPUT` を指定し、この準備を省略できます。

入力は次の形の配列です。`existingPeople` は任意で、同一本人・同一出典の既知の確認済み要約を再利用する場合だけ指定します。

```json
[{
  "municipalityCode": "01100",
  "municipalityName": "札幌市",
  "prefecture": "北海道",
  "name": "秋元克広",
  "snapshotAsOf": "2025-04-30",
  "officialURL": "https://www.city.sapporo.jp/",
  "existingPeople": []
}]
```

出力は全入力人物を含む配列です。人物の `municipalityCode/name/snapshotAsOf` を維持し、`findings` と `enrichment`（確認日、状態、試行URL、注記）を付けます。住所・電話・生年月日・家族構成は事実項目にしません。

## 環境変数

| 変数 | 意味・既定値 |
| --- | --- |
| `MAYORS_WORK_DIR` | 非公開の作業先。既定はOS一時ディレクトリ下 |
| `MAYORS_NATIONAL_INPUT` | 準備用の全国自治体JSON。既定は実行ディレクトリの `data/national.json` |
| `MAYORS_EXISTING_PEOPLE` | 準備時に任意で読み込む確認済み人物JSON配列。未指定では再利用なし |
| `MAYORS_INPUT` | 固定人物一覧。既定は作業先の `mayors.json` |
| `MAYORS_COLLECTED` | 通常取得結果。既定は作業先の `collected.json` |
| `MAYORS_CACHE` | 非公開のHTML・HTTP状態キャッシュ。既定は作業先の `cache` |
| `MAYORS_CHECKPOINT` | 再開用JSONL。既定は作業先の `checkpoint.jsonl` |
| `MAYORS_AUDITED` | 監査だけを実行した場合の出力。既定は作業先の `audited.json` |
| `MAYORS_OUTPUT` | 公開可能な最終JSON。既定は作業先の `enriched-mayors.json` |
| `MAYORS_REPORT` | 件数・一致・統合・私的情報検査の品質記録。既定は作業先の `quality-report.json` |
| `MAYORS_SUPPLEMENTS` | 統合する補足JSONのパス一覧。OSのパス区切り文字で連結。既定は同梱の `reviewed-supplements.json` |
| `MAYORS_CHECKED_AT` | 今回の通常調査・監査日（ISO日付）。既定は実行日。過去調査の再現ではその調査日を明示 |
| `MAYORS_EXPECTED_COUNT` | 完遂チェックの人数。既定1741。少数検証では入力人数に合わせる |
| `MAYORS_PARALLEL` | 異なるホストを含む全体並列数1–12。既定12、同一ホストは常に1接続 |
| `MAYORS_MAX_PAGES` | 1人のナビ追跡上限1–8。既定4 |
| `MAYORS_CA_BUNDLE` | 必要な場合の信頼済みCA証明書ファイル。未指定では標準の証明書検証 |
| `MAYORS_SEED_INDEX` / `MAYORS_SEED_DIR` | 任意の非公開保存HTMLを再照合する場合のTSV（名前・URL）とHTML保存先。未指定では利用なし |

各取得で新Clientを作成し、長寿命接続プールを再利用しません。HTTP再試行は最大1回、本文上限2.5MB。証明書検証を有効にしています。PDF、JavaScriptだけで表示するナビ、氏名が画像だけのページは自動処理できない場合があります。

```sh
# 中断後の再開。完了済みの未確認・取得失敗も再利用する点に注意。
python path/to/public-mayors/enrich-mayors.py --resume
# 監査だけを実行（ネットワーク取得なし）
python path/to/public-mayors/audit-mayors.py
```

新しい調査では新しい作業先を使ってください。`--resume` とキャッシュは過去の結果の再利用であり、新たなアクセス確認ではありません。通常取得直後のキャッシュを監査に使用します。本文キャッシュがない資料を、本文再確認済みとして扱いません。

## 本人判定と事実の扱い

フルネームを氏名欄・本人紹介見出し等で確認し、異体字の限定正規化と、明示確認済みの通称対応だけを認めます。単なる歴代首長一覧・前任者への言及・サイトのナビやフッタだけの一致は不採用です。副首長など別人の見出し以降を切り離します。

学歴・職歴・議会歴・団体/PTA役職を、年月が付いた短い行か明示の経歴欄から抽出し、最大25件程度まで残します。近接する任期や生年月日を卒業年月へ流用しません。過去の就任記載から現在の継続を断定せず、政策紹介を達成実績へ変換しません。

`asOf` は判読できた資料更新日です。更新日不明時は通常調査日を入れるため、経歴の発生年月は `period` を参照してください。`checkedAt` は調査日であり、補足の過去の確認日を現在の日付へ書き換えません。

取得失敗は経歴の不存在を意味しません。通常経路から接続できなくても他の閲覧経路では読める場合、その確認済みの短い補足を別途作成できます。

## 手動補足36名の再生成

`reviewed-supplements.json` は2026年11月5日にWebで照合した36名239件の**短い要約と出典URL**です。行政・団体公式、本人発信等を区別しています。資料本文や画像の複製は含みません。補足の中身は手動調査であり、同梱スクリプトだけでWebから自動的に再調査できるという意味ではありません。

```sh
# 同梱の確認済み要約を検証・整形して作業先へ再生成
python path/to/public-mayors/build-supplements.py
# 外部の新たな確認済み要約ファイルから再生成（--inputは複数可）
python path/to/public-mayors/build-supplements.py --input /path/to/review-a.json --input /path/to/review-b.json
```

入力は `MAYORS_SUPPLEMENT_INPUTS`、出力は `MAYORS_SUPPLEMENT_OUTPUT` でも指定できます。入力一覧の区切りは `MAYORS_SUPPLEMENTS` と同様です。同一人物の重複や未確認の氏名不一致は拒否します。出典を再読して要約・確認日を更新したうえで、新しい補足ファイルを統合対象に指定してください。

最終統合は入力のcode+name両方が完全一致する補足だけ採用します。同URL由来の通常抽出は手動補足へ置換し、別の公式出典の独自事実を残します。公開用の最終JSONでは監査用の原文断片 `sourceFragment` を削除します。

再取得では上流の変更・首長交代・接続成否により結果が変わります。2026年の調査結果を完全再現するには当時の非公開入力・キャッシュが必要であり、それらは本パッケージには同梱していません。公開済みの最終データ自体を書き換える必要はありません。
