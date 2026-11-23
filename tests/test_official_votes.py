import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('vote_pdf',Path(__file__).resolve().parents[1]/'scripts/sync_official_votes.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class VotePdfTests(unittest.TestCase):
 def setUp(self):
  self.sample='令和８年１１月２２日執行\n八街市長選挙開票結果\n確定\n1 無所属 木村 ゆきこ 6,833\n2 無所属 山本 よしかず 12,356\n'
 def test_complete_verified_votes(self):
  rows=m.parse(self.sample)
  self.assertEqual(len(rows),2)
  self.assertEqual([r['votes'] for r in rows],[6833,12356])
  self.assertEqual([r['result'] for r in rows],['not_elected','elected'])
 def test_cannot_overlook_missing_candidate(self):
  with self.assertRaises(ValueError):m.parse(self.sample.replace('2 無所属 山本 よしかず 12,356',''))
 def test_refuse_uncertified(self):
  with self.assertRaises(ValueError):m.parse(self.sample.replace('確定','速報'))
if __name__=='__main__':unittest.main()
