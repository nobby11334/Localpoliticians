import importlib.util,unittest
from pathlib import Path
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('sync_candidates',root/'scripts/sync_candidates.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class CandidateImportTests(unittest.TestCase):
 def setUp(self):
  self.conf={'authority':'election_commission','allowedEvidenceHosts':['www.city.example.jp']}
  self.codes={'13112'}
  self.row={'candidateName':'山田 太郎','municipalityCode':'13112','electionType':'mayor',
   'electionName':'世田谷区長選挙','status':'正式届出','sourceURL':'https://www.city.example.jp/notice',
   'publishedAt':'2026-11-23'}
 def test_valid_official_filing(self):
  self.assertEqual(m.validate(self.row,self.conf,self.codes)['status'],'正式届出')
 def test_office_not_current_role(self):
  self.assertEqual(m.to_person(m.validate(self.row,self.conf,self.codes))['candidate']['electionType'],'mayor')
 def test_party_cannot_certify_filing(self):
  with self.assertRaises(ValueError):m.validate(self.row,{**self.conf,'authority':'party'},self.codes)
 def test_unknown_municipality(self):
  with self.assertRaises(ValueError):m.validate({**self.row,'municipalityCode':'99999'},self.conf,self.codes)
 def test_untrusted_evidence(self):
  with self.assertRaises(ValueError):m.validate({**self.row,'sourceURL':'https://example.org/claim'},self.conf,self.codes)
 def test_untrusted_scheme(self):
  with self.assertRaises(ValueError):m.validate({**self.row,'sourceURL':'http://www.city.example.jp/notice'},self.conf,self.codes)
 def test_target_mismatch(self):
  with self.assertRaises(ValueError):m.validate({**self.row,'electionName':'世田谷区議会議員選挙'},self.conf,self.codes)
 def test_normalized_name(self):
  self.assertEqual(m.norm('山田　太郎'),'山田太郎')
 def test_missing_date(self):
  with self.assertRaises(ValueError):m.validate({**self.row,'publishedAt':'tomorrow'},self.conf,self.codes)
if __name__=='__main__':unittest.main()
