import importlib.util, unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('election_sync',Path(__file__).resolve().parents[1]/'scripts/sync_elections.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class ElectionValidationTests(unittest.TestCase):
    def setUp(self):
        self.source={'allowedEvidenceHosts':['www.city.example.jp']}
        self.record={'electionId':'test-2026','municipalityCode':'13105','electionDate':'2026-11-01','office':'council','candidateName':'山田 太郎','result':'elected','sourceURL':'https://www.city.example.jp/election/final','publishedAt':'2026-11-02','votes':1234}
    def test_valid(self): self.assertEqual(mod.validate(self.record,self.source)['votes'],1234)
    def test_untrusted_source(self):
        with self.assertRaises(ValueError):mod.validate({**self.record,'sourceURL':'https://evil.example.org/final'},self.source)
    def test_missing_evidence(self):
        with self.assertRaises(ValueError):mod.validate({**self.record,'sourceURL':''},self.source)
    def test_bad_status(self):
        with self.assertRaises(ValueError):mod.validate({**self.record,'result':'速報'},self.source)
    def test_loser_cannot_have_term(self):
        with self.assertRaises(ValueError):mod.validate({**self.record,'result':'not_elected','termStart':'2026-11-02'},self.source)
    def test_bad_votes(self):
        with self.assertRaises(ValueError):mod.validate({**self.record,'votes':-1},self.source)
if __name__=='__main__': unittest.main()
