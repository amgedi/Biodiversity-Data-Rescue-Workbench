import base64,copy,hashlib,os,struct,unittest
from pathlib import Path
from unittest.mock import patch
from importers import ingest
from doc_import import recovered
from doc_worker import read_story,literal_display,VERSIONS
from doc_fixtures import streams,fixture,ole
ROOT=Path(__file__).resolve().parents[1]

def source(data=None,name='fictional-legacy-notes.doc'):
 raw=(ROOT/'examples'/name).read_bytes() if data is None else data
 return {'name':name,'base64':base64.b64encode(raw).decode(),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

class LegacyWordTests(unittest.TestCase):
 def test_real_word_format_fictional_story_is_supporting_and_original_exact(self):
  original=source();before=copy.deepcopy(original);result=ingest({'source':original,'options':{}});self.assertEqual(original,before);self.assertEqual(result['tables'],[]);self.assertEqual(result['resource']['role'],'supporting');self.assertIsNone(result['resource']['conversionIssue']);self.assertEqual(result['resource']['base64'],original['base64']);preview=result['resource']['archaeology']['documentPreview'];self.assertEqual(''.join(b['rawText'] for b in preview['blocks']),('Fictional wetland: NA meaning is unknown.').ljust(47)+'\r');self.assertEqual(preview['mainStoryCpCount'],48);self.assertEqual(preview['blocks'][0]['cpEnd'],48);self.assertFalse(preview['legacyWord']['macrosExecuted']);self.assertFalse(preview['legacyWord']['revisionsResolved']);self.assertFalse(preview['legacyWord']['faithfulDocumentReconstruction']);self.assertEqual(preview['reader']['containerVersion'],'2.0.2')
 def test_unicode_control_markers_and_compressed_mapping(self):
  result=recovered(fixture());self.assertNotIn('error',result);self.assertIn('湿地 · Frog 🐸',result['blocks'][1]['rawText']);self.assertEqual(result['blocks'][1]['cpEnd']-result['blocks'][1]['cpStart'],len(result['blocks'][1]['rawText'].encode('utf-16-le'))//2);self.assertIn('⟦U+0013⟧LINK fictional⟦U+0014⟧literal⟦U+0015⟧',result['blocks'][2]['text']);self.assertEqual(literal_display('\u202E'), '⟦U+202E⟧')
  word,table=streams(parts=[('\x80\x82\x8e\x91\r',True)]);text=read_story(word,table)['blocks'][0]['rawText'];self.assertEqual(text,'\x80‚\x8e‘\r')
 def test_known_fib_versions_and_zero_table_stream(self):
  for version in VERSIONS:
   word,table=streams(version=version);result=read_story(word,table);self.assertEqual(result['fibVersion'],hex(version))
  word,table=streams();word=bytearray(word);struct.pack_into('<H',word,10,0x1000);result=recovered(ole(bytes(word),table,'0Table'));self.assertNotIn('error',result);self.assertEqual(result['tableStream'],'0Table')
 def test_protected_corrupt_and_unsupported_sources_preserved_without_text(self):
  candidates=[fixture(encrypted=True),b'fictional damaged Word file']
  word,table=streams();bad=bytearray(word);struct.pack_into('<H',bad,2,0x65);candidates.append(ole(bytes(bad),table))
  for data in candidates:
   original=source(data);result=ingest({'source':original,'options':{}});self.assertEqual(result['tables'],[]);self.assertEqual(result['resource']['base64'],original['base64']);self.assertTrue(result['resource']['conversionIssue']);self.assertEqual(result['resource']['archaeology']['documentPreview']['blocks'],[])
  self.assertEqual(recovered(candidates[0])['error'],'DOC_ENCRYPTED')
 def test_invalid_piece_lengths_positions_and_counts_reject_complete_recovery(self):
  word,table=streams(parts=[('Fictional\r',True)]);variants=[]
  bad=bytearray(table);struct.pack_into('<I',bad,9,0);variants.append((word,bytes(bad)))
  bad=bytearray(table);struct.pack_into('<I',bad,15,0x40000000|0x3FFFFFFE);variants.append((word,bytes(bad)))
  variants.append((word,table[:-1]));bad=bytearray(word);struct.pack_into('<I',bad,76,1000001);variants.append((bytes(bad),table));bad=bytearray(word);struct.pack_into('<I',bad,64,10);variants.append((bytes(bad),table))
  for w,t in variants:
   with self.assertRaises(ValueError):read_story(w,t)
 def test_utf16_split_surrogate_pair_is_joined_and_invalid_unicode_rejected(self):
  word,table=streams(parts=[('🐸\r',False)]);base=bytearray(word);fc=2048;plc=struct.pack('<3I',0,1,3)+struct.pack('<HIH',0,fc,0)+struct.pack('<HIH',0,fc+2,0);table=b'\x02'+struct.pack('<I',len(plc))+plc;struct.pack_into('<I',base,154+33*8+4,len(table));self.assertEqual(read_story(bytes(base),table)['blocks'][0]['rawText'],'🐸\r')
  base[2048:2050]=b'\x00\xDC'
  with self.assertRaisesRegex(ValueError,'DOC_TEXT'):read_story(bytes(base),table)
 def test_bounded_preview_keeps_exact_cp_ranges_and_reports_omitted_blocks(self):
  word,table=streams(parts=[('x'*5000+'\r'+'short\r'*220,False)]);result=read_story(word,table);self.assertEqual(len(result['blocks']),200);self.assertEqual(result['omittedBlocks'],21);self.assertTrue(result['blocks'][0]['truncated']);self.assertEqual(result['blocks'][0]['cpEnd'],5001);self.assertEqual(result['blocks'][0]['previewCpEnd'],4000);self.assertEqual(result['blocks'][1]['cpStart'],5001)
 def test_property_records_bounded_and_not_interpreted(self):
  word,table=streams(properties=b'\x01\x02\x00\x00\x00');result=read_story(word,table);self.assertEqual(result['skippedPropertyRecords'],1);self.assertFalse(result['legacyWord']['propertiesInterpreted'])
  word,table=streams(properties=b'\x01\xff\xff')
  with self.assertRaisesRegex(ValueError,'DOC_PIECES'):read_story(word,table)
 def test_supporting_only_integrity_and_busy_boundaries(self):
  with patch('doc_import.recovered',side_effect=AssertionError('Do not parse')):self.assertEqual(ingest({'source':source(),'options':{'preserveOnly':True}})['tables'],[])
  with patch('doc_import.verify_vendor',side_effect=ValueError('XLS_READER_INTEGRITY')):self.assertEqual(recovered(fixture())['error'],'DOC_READER_INTEGRITY')
  with patch('doc_import._slots') as slots:
   slots.acquire.return_value=False;self.assertEqual(recovered(fixture())['error'],'DOC_BUSY');slots.release.assert_not_called()
 @unittest.skipUnless(os.name=='nt','Windows process-limit failure boundary')
 def test_required_job_failure_kills_child_before_original_temp_cleanup(self):
  with patch('doc_import.subprocess.Popen') as popen,patch('doc_import.WindowsJob',side_effect=OSError('Limit failure')):
   process=popen.return_value;process.poll.return_value=0;self.assertEqual(recovered(fixture())['error'],'DOC_LIMIT_UNAVAILABLE');process.kill.assert_called_once();process.communicate.assert_called_once()

if __name__=='__main__':unittest.main()
