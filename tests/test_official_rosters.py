import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('official',Path(__file__).resolve().parents[1]/'scripts/sync_official_rosters.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class OfficialRosterTest(unittest.TestCase):
 def setUp(self):
  self.conf={'documentTitle':'犬山市長選挙','finalMarker':'確定','minCandidates':2,'maxCandidates':2}
  self.sample='犬山市長選挙　立候補受付状況報告書　※確定\n1 小西 ひこじ 兵庫県伊丹市　無所属\n2 原 よしのぶ 愛知県犬山市 無所属\n'
 def test_extract_candidates(self):
  self.assertEqual(m.parse_document(self.sample,self.conf),['小西ひこじ','原よしのぶ'])
 def test_refuse_partial_extraction(self):
  with self.assertRaises(ValueError):m.parse_document(self.sample.replace('2 原 よしのぶ','4 原 よしのぶ'),self.conf)
 def test_refuse_nonfinal(self):
  with self.assertRaises(ValueError):m.parse_document(self.sample.replace('確定','速報'),self.conf)
 def test_refuse_missing_second_candidate(self):
  with self.assertRaises(ValueError):m.parse_document(self.sample.splitlines()[0]+'\n'+self.sample.splitlines()[1],self.conf)
if __name__=='__main__':unittest.main()
