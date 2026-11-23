# 選挙結果の自動連携（2026-11）
既存の全国名簿（2025-04-30資料時点）は上書きしません。確認済み選挙結果を `data/election-results.json` に時系列で保存し、自治体ページに表示します。首長の「選挙結果に基づく任期開始確認済み」表示は、当選者の `termStart` が到来し `termEnd` が未到来のときだけ表示します。名簿の古い首長は履歴として残します。
## データの取得先
`data/election-sources.json` の `sources` に、**選管が公開する機械可読な確定開票結果データ**のHTTPS URLを登録してください。現時点で登録された配信元は0件です。全国統一の選管APIはないため、この取得元の登録が済むまで選挙結果は自動増加しません。GitHub Actionsは毎日実行する設定です。
```json
{
  "sources": [
    {
      "id": "example-municipality-election",
      "enabled": false,
      "format": "json",
      "url": "https://example.jp/official-final-results.json",
      "allowedEvidenceHosts": ["example.jp"]
    }
  ]
}
```
JSONは配列、または `{"results":[...]}` を受け付けます。CSVは同一フィールド名をヘッダーにしてください。上のURLは仕様例であり、実在する配信元ではありません。
## 必須項目
`electionId`（一意の選挙識別子）、`municipalityCode`（5桁自治体コード）、`electionDate`（YYYY-MM-DD）、`office`（mayor/council）、`candidateName`、`result`（elected/not_elected）、`sourceURL`（選管公式発表URL）、`publishedAt`（YYYY-MM-DD）。
任意項目は `votes`（数値）、`termStart`、`termEnd`、`district`、`uncontested`、`personId`。候補者ページへ選挙結果を結び付けるには、資料に基づき生成済み人物IDと一致する `personId` を指定してください。同名という理由だけでは自動結合しません。選挙結果を掲載しただけでは現職認定しません。議員も、当選のみでは現職認定せず、就任の管理は将来の改善対象です。
## 安全対策
取得元ホストと出典ホストを許可リストで制限し、必須項目と日時形式を検証します。選挙の結果の当落が過去の確認済み資料と食い違う場合は自動上書きせず、失敗として保持します。取得失敗時も過去の成功結果を残します。公式の選挙確定・訂正・当選無効・繰上当選等は、配信元が最終結果へ正規化してから取り込む方式です。
**この実装は全国の選管サイトのHTML/PDFを自律的に解析するものではありません。** 配信元の登録・変換アダプターの整備が次工程です。
