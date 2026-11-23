import importlib.util,sys,unittest
from pathlib import Path
SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
spec=importlib.util.spec_from_file_location('official_html',SCRIPTS/'sync_official_html_results.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class OfficialHTMLTests(unittest.TestCase):
 def test_mayor_results(self):
  html='<h1>滝沢市選挙開票結果（確定）</h1><table><tr><th>氏名</th><th>党派</th><th>得票数</th><th>当選人</th></tr><tr><td>武田 さとる</td><td>無所属</td><td>13,096</td><td>当選人</td></tr><tr><td>おくつ かずとし</td><td>無所属</td><td>4,750</td><td></td></tr></table>'
  conf={'layout':'named','expected':['武田さとる','おくつかずとし'],'identity':{'武田さとる':'武田哲','おくつかずとし':'奥津一俊'},'municipalityCode':'03216','electionId':'03216-mayor-2026-11-15','electionDate':'2026-11-15','office':'mayor','publishedAt':'2026-11-16','url':'https://example.org/official'}
  result=m.parse(html,conf)
  self.assertEqual(len(result),2)
  self.assertEqual(result[0]['votes'],13096)
  self.assertEqual(result[0]['result'],'elected')
  self.assertEqual(result[0]['personId'],'03216-ca00f4e44ab1')
 def test_missing_winner_refused(self):
  html='<h2>開票結果</h2><table><tr><td>武田 さとる</td><td>無所属</td><td>13,096</td><td></td></tr><tr><td>おくつ かずとし</td><td>無所属</td><td>4,750</td><td></td></tr></table>'
  conf={'layout':'named','expected':['武田さとる','おくつかずとし'],'identity':{'武田さとる':'武田哲','おくつかずとし':'奥津一俊'},'municipalityCode':'03216','electionId':'x','electionDate':'2026-11-15','office':'mayor','publishedAt':'2026-11-16','url':'https://example.org/official'}
  with self.assertRaises(ValueError):m.parse(html,conf)
if __name__=='__main__':unittest.main()
