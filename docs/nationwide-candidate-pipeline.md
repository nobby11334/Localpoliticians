# 全国候補者・選挙結果の継続更新（2026-11-23）
## 動作する仕組み
- `scripts/audit_candidates.py`: 全国1,741市区町村の候補者収録を監査。28分割の日次ニュース探索から確認待ち記事を蓄積。記事は事実認定しない。
- `review.html`: 未収録自治体、巡回失敗、要確認記事を自治体や都道府県で検索できる。
- `scripts/sync_candidates.py`: 選管・政党・候補予定者の**機械可読な構造化一次資料**を取り込み、自治体コード／氏名／選挙名／発表日／URL／配信元を検証し、`data/imports/verified-candidates.json` へ永続保存。取得失敗時も成功履歴を保持。
- `scripts/sync_elections.py`: 既存の確定当落と任期の取り込み処理。証拠なしの同名マージはしない。
- GitHub Actions: 日次のデータ取得、名簿生成、監査、公表。
## データソースの制約
`data/candidate-sources.json` と `data/election-sources.json` は**現時点で sources が空**。全国の選管に共通した候補者・開票結果の機械可読な公式APIは用意されていないため、実データの継続的な自動追加は未稼働。各自治体・都道府県・政党の公式データを同一スキーマに変換するアダプターを作り、ソースを登録することが必要。報道だけで「正式な候補者」や「当選」とは決めない。
## 公式候補者フィード登録
```json
{
 "sources": [{
   "id": "official-feed-id",
   "enabled": false,
   "authority": "election_commission",
   "url": "https://example.jp/candidates.json",
   "format": "json",
   "allowedEvidenceHosts": ["example.jp"]
 }]
}
```
実在する配信先と根拠資料が確認できるまで、有効化しないこと。JSONは配列または `{"candidates":[...]}`、CSVは同じ名前の列を使う。必須列は `municipalityCode,candidateName,electionType,electionName,status,sourceURL,publishedAt`。任意は `electionDate,party,sourceTitle`。electionType は mayor/council。status は「本人表明」「公認発表」「推薦発表」「正式届出」。正式届出は選管の公式配信に限る。
## 完了条件と未達
全国の候補者を完全網羅したとの主張はできない。全国の巡回は候補者不在の証明にならない。確認待ち記事を精査して根拠となる発表を見付けること、当落を含む公式配信先を登録すること、退任・繰上当選・選挙無効などの根拠付き状態遷移を完成させることが残る。
