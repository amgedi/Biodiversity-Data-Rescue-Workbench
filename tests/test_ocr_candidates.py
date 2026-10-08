import base64,hashlib,unittest,copy
from unittest.mock import patch
from ocr_candidates import parse_tsv,preview,capability
HEADER='level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n'
def word(value='001',confidence='95.5',page='1'):return ('5\t'+page+'\t1\t1\t1\t1\t10\t20\t30\t40\t'+confidence+'\t'+value+'\n')
class OcrTests(unittest.TestCase):
 def test_candidates_preserve_literal_and_raw_provider_score_without_confirmation(self):
  result=parse_tsv((HEADER+word('001')+word('0')+word('NA')+word('<script>')).encode());self.assertEqual([w['text'] for w in result['words']],['001','0','NA','<script>']);self.assertEqual(result['words'][0]['boxPixels'],[10,20,30,40]);self.assertEqual(result['words'][0]['providerConfidence'],95.5);self.assertTrue(all(w['scientificConfirmation'] is False for w in result['words']))
 def test_bad_scores_multiframe_and_malformed_output_are_refused(self):
  for value in ['nan','inf','-1','101','not a score']:
   with self.assertRaises(ValueError):parse_tsv((HEADER+word(confidence=value)).encode())
  with self.assertRaisesRegex(ValueError,'UNSUPPORTED'):parse_tsv((HEADER+word(page='2')).encode())
  with self.assertRaises(ValueError):parse_tsv(b'unknown\tcolumns\n')
 def test_word_and_character_bounds_report_omissions(self):
  result=parse_tsv((HEADER+word()*2100).encode());self.assertEqual(len(result['words']),2000);self.assertEqual(result['omittedWords'],100)
 def test_opt_in_integrity_and_absent_provider_preserve_source(self):
  raw=b'\x89PNG\r\n\x1a\nfictional';source={'id':'fictional-image','name':'image.png','sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'base64':base64.b64encode(raw).decode()};before=copy.deepcopy(source)
  with self.assertRaisesRegex(ValueError,'OPT_IN'):preview(source)
  with patch('ocr_candidates.provider_path',return_value=None):
   self.assertFalse(capability()['available'])
   with self.assertRaisesRegex(ValueError,'UNAVAILABLE'):preview(source,True)
  self.assertEqual(source,before)
  with self.assertRaisesRegex(ValueError,'INTEGRITY'):preview({**source,'sha256':'0'*64},True)
