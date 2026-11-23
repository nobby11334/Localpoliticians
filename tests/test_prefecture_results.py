import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('pref_result',Path(__file__).resolve().parents[1]/'scripts/sync_prefecture_results.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class PrefectureResultTests(unittest.TestCase):
 def test_approved_winner_only(self):
  html='<table><tr><th>市町村名</th><th>任期満了日</th><th>告示日</th><th>投票日</th><th>投票率</th><th>当選者</th><th>当選回数</th><th>備考</th></tr><tr><td>五泉市</td><td>1月28日</td><td>1月18日</td><td>1月25日</td><td>無投票</td><td>田辺正幸</td><td>2</td><td></td></tr><tr><td>田上町</td><td>6月21日</td><td>5月26日</td><td>5月31日</td><td>66%</td><td>佐野恒雄</td><td>3</td><td></td></tr><tr><td>津南町</td><td>7月8日</td><td>6月23日</td><td>6月28日</td><td>74%</td><td>根津和博</td><td>1</td><td></td></tr></table>'
  rows=m.extract(html,{'五泉市':'15218','田上町':'15361','津南町':'15482'})
  self.assertEqual(len(rows),3)
  self.assertEqual(rows[0]['candidateName'],'田辺正幸')
  self.assertEqual(rows[0]['result'],'elected')
  self.assertTrue(rows[0]['uncontested'])
  self.assertEqual(rows[1]['electionDate'],'2026-05-31')
 def test_incomplete_table_refused(self):
  with self.assertRaises(ValueError):m.extract('<table><tr><th>市町村名</th></tr></table>',{'五泉市':'15218'})
if __name__=='__main__':unittest.main()
