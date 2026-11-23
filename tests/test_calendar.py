import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('calendar_sync',Path(__file__).resolve().parents[1]/'scripts/sync_calendar.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class CalendarTests(unittest.TestCase):
 def test_jis_six_digit_to_five(self):
  self.assertEqual(m.normalize_code('011002'),'01100')
 def test_invalid_code(self):
  self.assertIsNone(m.normalize_code('foo'))
 def test_missing_data(self):
  self.assertIsNone(m.valid_date(''))
 def test_invalid_date(self):
  self.assertIsNone(m.valid_date('2026-19-40'))
 def test_entry(self):
  row={'団体コード':'131121','都道府県':'東京都','市区町村':'世田谷区','次の首長選挙の投票日':'2027-04-25','最終確認日':'2026-11-21','出典つきのページ':'https://senkyo-data.jp/municipalities/131121/elections/mayor/'}
  code,r=m.to_entry(row,{'13112'})
  self.assertEqual(code,'13112')
  self.assertEqual(r['nextMayorElection'],'2027-04-25')
  self.assertIsNone(r['nextCouncilElection'])
 def test_untrusted_reference_omitted(self):
  code,r=m.to_entry({'団体コード':'011002','出典つきのページ':'https://unsafe.invalid'}, {'01100'})
  self.assertEqual(r['referenceURL'],'')
if __name__=='__main__':unittest.main()
