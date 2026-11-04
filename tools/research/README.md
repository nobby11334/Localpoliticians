# 再調査用の取得・抽出スクリプト

このディレクトリへ移動して実行してください。各スクリプトは取得元のHTML構造が変わると再確認が必要です。公開人物情報の根拠を確認するための補助で、出力を無検証で本番へ上書きする用途ではありません。

```sh
cd tools/research
python -m pip install -r requirements.txt
python refresh-party-members.py --refresh
python collect-council-central.py --refresh
python enrich-central.py
mkdir -p west-cache
python build-west.py --refresh
python enrich-west.py
python fetch-east.py
python fetch-east-more.py
python parse-east.py
python fetch-komei.py
python fetch-profiles.py
python build-mayor-careers.py
```

PDF・XLSXの抽出にPopplerのpdftotextとopenpyxlを利用する処理があります。元資料やHTMLキャッシュには議員の住所・電話等が含まれる場合があるため、公開リポジトリへ追加しないでください。成果JSONは公開職務・所属・経歴等に限定しています。

首長の `curated-findings.tsv` は2026年11月4日に人手で確認した記録です。再取得後に氏名が変わった場合、旧首長の経歴を新首長へ自動転用してはいけません。候補情報は `python rebuild_candidates.py --registry ../../data/national.json --output ./candidates-rebuilt.json` で再取得できます。抽出手順・除外条件は `CANDIDATE_RESEARCH.md`、取得範囲は `candidates-research-report.json` を参照してください。

取得後は出典・氏名・自治体コード・資料日・現職/予定者の区分を確認し、承認できたJSONのみ `data/imports/` へ移してください。`npm run build` が自治体別の人物データと収録範囲を再生成します。`npm test` で整合性を検査できます。

一部の名簿は特定政党の掲載議員のみです。人数を自治体の定数や政党勢力と誤認しないでください。氏名のひらがな・漢字・通称表記の差は、同一人物と確認できる根拠なしに自動統合していません。
