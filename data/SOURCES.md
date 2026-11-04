# 全国自治体・首長基礎データ

`data/national.json` は全国1741市区町村の自治体コード、名称、都道府県、公式ホームページURL、2025年4月30日時点の首長氏名を格納する。

## 出典と範囲

- 自治体コード・名称: デジタル庁 Japan Dashboard 地方財政（市町村ごと）、2026-04-24公開。初回生成では既存の地方財政データ1741件を使用。再生成スクリプトは下記localgovjpから政令指定都市の行政区を除外し、同じ1741自治体コードを再構成する。
- 首長名簿: 公益財団法人 地方自治総合研究所『全国首長名簿2025』、基準日2025-04-30。公開2026-01-15、PDFファイル2026-05-14差替版。 https://jichisoken.jp/jichitaisenkyo/2025/
- 全国首長PDF: https://jichisoken.jp/file/jichitaisenkyo/No142_010-025_20260514.pdf （865,388bytes）
- 公式URL: Code for Fukui localgovjp（国土地理院・J-LISを原典として記載、CC0）。READMEの更新履歴は2026-07-09。 https://code4fukui.github.io/localgovjp/localgovjp.json （672,342bytes、政令指定都市の区等を含む1916件から1741件をコード照合）。J-LIS本体からの一括取得は403応答で断念。

## 品質確認

1. PDFをpdftotext -rawで抽出。47都道府県の見出しと自治体名を1741件のコードに一致させた。
2. 六ケ所/六ヶ所、駒ケ根/駒ヶ根、飛驒/飛騨、諌早/諫早、沖繩/沖縄などの表記を統一。
3. 改姓併記の4自治体は括弧内の公開通称を表示。
4. PDFの埋込フォントは28件で欠字、文字の重複、通称等の差が生じた。2021–2025年の各基礎Excel「首長」シートで当選行を自治体コード別に照合し、1733自治体はExcelの氏名で補完した。名簿上の在職者と照合する目的に限定し、選挙日・所属等は取り込まない。
5. 残り8自治体（相模原市、新潟市、長野県高山村、堺市、奈良県川上村、岡山市、熊本市、熊本県小国町）はPDFの正常な氏名を採用。欠字記号なし、1741件のコードが一意で全国自治体ディレクトリとの差分なし。

## 表示上の条件

全件 `asOf:2025-04-30`, `quality:資料時点（現職未確認）`。2026-11-04時点の現職を意味しない。変更や選挙結果が確認された自治体は、一次資料の日付とURLを付けて差し替えること。PTA、理事、政党、政策団体、経歴はこの資料から推測しない。

研究所基礎Excelの日時セルには選挙執行年列と異なる年が設定された行があるため、日時セルをそのまま採用しないこと。

## 最新行政資料候補

- 北海道選管 https://www.pref.hokkaido.lg.jp/hs/68024.html : 2026-10-26現在、市町村長名簿XLSX29.2KB、任期一覧XLSX20.3KB。shell直取得は503応答。
- 秋田県CKAN https://ckan.pref.akita.lg.jp/tl/dataset/050008_sicyouson_007 : 2026-08-26、市町村長一覧XLSX/CSV。
- 千葉県 https://www.pref.chiba.lg.jp/shichou/gyousei/meibo.html : 2026-09-13現在、首長PDF68.7KB。
- 福岡県 https://www.pref.fukuoka.lg.jp/contents/senkyo-ichiran.html : 2026-09-18更新、首長名簿PDF350KB。
- 福島県 https://www.pref.fukushima.lg.jp/sec/01145a/ninki.html : 2026-10-01現在、名簿PDF425KB。
- 沖縄県 https://www.pref.okinawa.jp/kensei/senkyo/1023172/1005019.html : 2026-10-30現在、任期一覧XLS53.5KB/PDF156.6KB。
- 鳥取県 https://www.pref.tottori.lg.jp/12519.htm : 2026-10-19現在、19首長、HTML表。
- 富山県 https://www.pref.toyama.jp/140403/kensei/shichouson/gyouzaisei/kj00000238.html : 2026-10-26更新、首長名・任期、HTML表。
- 愛知県 https://www.pref.aichi.jp/soshiki/shichoson/0000046285.html : 2026-09-13現在、HTML。

全国議会議員の個人名を網羅する無料の一次行政データは今回の調査では見つからなかった。研究所Excel「議会」は主に党派別人数・選挙集計で、個人名簿には使えない。

## 再生成手順

Python 3.10以上、Pythonパッケージ `openpyxl`、Popplerの `pdftotext` が必要。Debian/Ubuntuでは次のように用意できる。

```sh
python -m pip install openpyxl
sudo apt-get install poppler-utils
python scripts/import-national.py --output /tmp/national-rebuilt.json
```

`--output` は必須。スクリプトは公開中のJSONを自動上書きしない。結果と `data/national.json` の差分をレビューし、必要な変更だけを反映する。元PDF・Excel・ディレクトリJSONは標準で `/tmp/localpoliticians-national` にキャッシュされ、再実行では再利用される。保存先は `--cache` で指定できる。再取得したい場合は対象キャッシュを除去して再実行する。ダウンロードしたPDFやExcelをGitへコミットする必要はない。

入力URLはスクリプトの `PDF_URL`、`DIRECTORY_URL`、`EXCEL_URLS` に固定してある。

| 資料 | URL | 取得サイズ |
| --- | --- | ---: |
| 市町村・特別区長名簿PDF | https://jichisoken.jp/file/jichitaisenkyo/No142_010-025_20260514.pdf | 865,388 bytes |
| 2021年基礎Excel | https://jichisoken.jp/file/jichitaisenkyo/2021_shikucyouson_20221220.xlsx | 1,057,566 bytes |
| 2022年基礎Excel | https://jichisoken.jp/file/jichitaisenkyo/2022_shikucyouson_20260514.xlsx | 1,006,065 bytes |
| 2023年基礎Excel | https://jichisoken.jp/file/jichitaisenkyo/2023_shikucyouson_20240422.xlsx | 1,312,693 bytes |
| 2024年基礎Excel | https://jichisoken.jp/file/jichitaisenkyo/2024_shikucyouson_20250219.xlsx | 317,316 bytes |
| 2025年基礎Excel | https://jichisoken.jp/file/jichitaisenkyo/2025_shikucyouson_20260106.xlsx | 390,638 bytes |
| 公式URL付き自治体ディレクトリ | https://code4fukui.github.io/localgovjp/localgovjp.json | 672,342 bytes |

上流ファイルが差し替わる可能性があるため、将来の取得内容の完全一致は保証しない。コードでは自治体数1741、コード一意性、PDF全件抽出、欠字の不存在を検査し、不一致時に停止する。初回の再生成確認では、既存 `data/national.json` と全1741自治体の行が完全一致した。`retrievedAt` のみ再生成日になる。

このスクリプトは2025年4月30日の史料スナップショットの再生成用であり、現在の在職者を発見する更新処理ではない。日々のリンク監視や行政資料からの最新情報反映とは区別する。


## 議員・経歴・次回選挙の全国拡充（2026-11-04）

`data/imports/` に取得時点の調査成果、`tools/research/` に再取得・抽出処理、報告書を保存。行政・議会の名簿、政党の所属議員名簿、2027年等の公式公認・推薦発表、行政および本人のプロフィールを資料として使用しています。現在の集計は `data/coverage.json` を参照してください。

- `council-east.json`: 北海道・東北・関東11自治体の公式議会名簿595人。札幌市議会事務局政策調査課のデータはCC BY 4.0で利用・抽出加工。本人HPの経歴は本人発信として記録。
- `council-central.json`: 中部・近畿25自治体の公式議会名簿1,059人。草津市は公式紹介ページに掲載された20人のみ。西宮市は取得失敗で未収録。
- `council-west.json`: 中国・四国・九州27市の公式議会名簿1,005人。別府市の政策は議員本人の記載。質問・委員会役職を政策成果と同一視しません。
- `party-members.json`: 日本共産党・国民民主党の公式名簿に掲載された市区町村議員2,394人。府県議を除外。名簿掲載日時不明・取得日を別表示。
- `komei-members.json`: 公明党の公式所属議員検索から市区町村の掲載者2,637人。府県議・国会議員を除外。個人ホームページは党公式プロフィールにリンクがある場合のみ転記。
- `candidates.json`: 自民党東京都連、日本維新の会、立憲民主党、公明党福岡、国民民主党東京都連、都民ファーストの会、日本保守党の公式発表等836人。次回の予定者資料に限定。推薦を党籍と推定せず、正式な届出候補者名簿とも区別。
- `mayor-careers.json`: 47都道府県・51自治体の自治体公式プロフィールによる首長の職歴・学歴、地域活動、団体役職、政策方針。元名簿の氏名を新首長へ自動転用しない。

統合は自治体コードと空白・Unicode互換表記を正規化した氏名をキーにします。﨑/崎・髙/高・塚/塚の差を統一し、出典表記も残します。ひらがな・通称と漢字名は、同一人物と確認できる根拠なしに統合しないため、重複掲載が残る可能性があります。件数は人物レコード数で、全国の現職総数・議会定数や政党勢力を意味しません。各資料の時点も異なります。

議会の会派から党籍を推定していません。議員・名誉職等の在任、報酬、実際の活動、成果の帰属は記載の範囲以外は未確認。未収録を経歴・活動・出馬がないことの証拠にはできません。
