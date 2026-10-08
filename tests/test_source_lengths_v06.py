import tempfile,unittest,copy
from pathlib import Path
from storage import Store
from test_upgrade import sample
class SourceLengthTests(unittest.TestCase):
 def test_length_and_identity_are_verified_even_when_checksums_still_match(self):
  with tempfile.TemporaryDirectory() as folder:
   store=Store(folder);p=store.save(sample());source=p['resources'][0];good=store.verify(p)[0];self.assertEqual(good['resourceId'],source['id']);self.assertTrue(good['backupByteLengthMatches']);self.assertTrue(good['diskByteLengthMatches']);p['resources'][0]['bytes']+=1;bad=store.verify(p)[0];self.assertTrue(bad['backupMatches']);self.assertFalse(bad['backupByteLengthMatches']);self.assertFalse(bad['diskByteLengthMatches'])
 def test_disk_tampering_is_reported_without_overwriting_evidence(self):
  with tempfile.TemporaryDirectory() as folder:
   store=Store(folder);p=store.save(sample());source=p['resources'][0];path=store.objects/source['sha256'];path.write_bytes(b'tampered');before=path.read_bytes();bad=store.verify(p)[0];self.assertFalse(bad['diskMatches']);self.assertFalse(bad['diskByteLengthMatches']);self.assertEqual(path.read_bytes(),before)
