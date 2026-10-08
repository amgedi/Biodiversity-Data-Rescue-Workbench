import base64,copy,hashlib,json,os,subprocess,unittest
from pathlib import Path
from unittest.mock import patch
from importers import ingest
from xls_import import recovered,verify_vendor
ROOT=Path(__file__).resolve().parents[1]


def source(name='fictional-legacy.xls',data=None):
 raw=(ROOT/'examples'/name).read_bytes() if data is None else data
 return {'name':name,'base64':base64.b64encode(raw).decode(),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}


class LegacyExcelTests(unittest.TestCase):
 def test_cached_values_hidden_records_types_and_original_bytes_preserved(self):
  original=source();before=copy.deepcopy(original);result=ingest({'source':original,'options':{}});self.assertEqual(original,before);self.assertEqual(result['resource']['base64'],original['base64']);self.assertEqual(result['resource']['sha256'],original['sha256']);self.assertEqual(result['resource']['bytes'],original['bytes']);self.assertEqual([t['name'] for t in result['tables']],['observations','codebook']);rows=result['tables'][0]['rows'];self.assertEqual(rows[0],['001','0.0','43832.0','1','','Fictional frog']);self.assertEqual(rows[1],['NA','-999.0','60.0','0','',' leading space ']);a=result['resource']['archaeology'];self.assertEqual(a['dateSystem'],'1900');self.assertEqual(a['sheets'][0]['hiddenRows'],[3]);self.assertEqual(a['sheets'][0]['hiddenColumns'],[6]);self.assertEqual(a['sheets'][0]['cellTypes'][1][2],3);self.assertEqual(a['sheets'][0]['cellTypes'][1][3],4);self.assertEqual(a['sheets'][1]['state'],'hidden');self.assertEqual(len(a['sheets'][1]['mergedCells']),1);self.assertTrue(a['sheets'][2]['empty']);self.assertFalse(a['legacyExcel']['formulasRecalculated']);self.assertFalse(a['legacyExcel']['macrosExecuted']);self.assertEqual(a['reader']['version'],'2.0.2');self.assertIsNone(result['resource']['conversionIssue'])
 def test_1904_epoch_is_recorded_without_date_interpretation(self):
  result=ingest({'source':source('fictional-legacy-1904.xls'),'options':{}});self.assertEqual(result['resource']['archaeology']['dateSystem'],'1904');self.assertEqual(result['tables'][0]['rows'],[['42370.0']]);self.assertEqual(result['tables'][0]['parsing']['dateSystem'],'1904')
 def test_reviewed_headers_and_invalid_options_never_return_partial_tables(self):
  result=ingest({'source':source(),'options':{'headersBySheet':{'observations':2}}});self.assertEqual(result['tables'][0]['originalHeaders'][0],'001');self.assertEqual(result['tables'][0]['rows'][0][0],'NA')
  for options in [{'headerRow':1000},{'headerRow':True},{'headersBySheet':{'observations':0}},{'encoding':'guessed-encoding'}]:
   with self.subTest(options=options):
    result=ingest({'source':source(),'options':options});self.assertEqual(result['tables'],[]);self.assertTrue(result['resource']['conversionIssue']);self.assertTrue(result['resource']['archaeology']['legacyExcel']['conversionBlocked'])
 def test_oversized_and_damaged_files_remain_exact_supporting_sources(self):
  for original in [source('fictional-legacy-wide.xls'),source(data=b'not an Excel workbook')]:
   result=ingest({'source':original,'options':{}});self.assertEqual(result['tables'],[]);self.assertEqual(result['resource']['base64'],original['base64']);self.assertEqual(result['resource']['sha256'],original['sha256']);self.assertEqual(result['resource']['role'],'supporting')
 def test_reader_integrity_and_support_only_failure_boundaries(self):
  verify_vendor()
  with patch('xls_import.verify_vendor',side_effect=ValueError('XLS_READER_INTEGRITY')):
   result=ingest({'source':source(),'options':{}});self.assertEqual(result['tables'],[]);self.assertEqual(result['resource']['archaeology']['legacyExcel']['reasonCode'],'XLS_READER_INTEGRITY')
  with patch('xls_import.recovered',side_effect=AssertionError('Must not parse supporting evidence')):
   result=ingest({'source':source(),'options':{'preserveOnly':True}});self.assertEqual(result['tables'],[]);self.assertEqual(result['resource']['base64'],source()['base64'])
 def test_modified_reader_hash_is_rejected_before_parsing(self):
  manifest=json.loads((ROOT/'vendor-xls/manifest.json').read_text(encoding='utf-8'));first=next(iter(manifest['files']));manifest['files'][first]['sha256']='0'*64
  with patch('xls_import.json.loads',return_value=manifest):
   with self.assertRaisesRegex(ValueError,'XLS_READER_INTEGRITY'):verify_vendor()
 def test_busy_recovery_preserves_exact_original_without_claiming_values(self):
  with patch('xls_import._slots') as slots:
   slots.acquire.return_value=False;result=ingest({'source':source(),'options':{}});self.assertEqual(result['tables'],[]);self.assertEqual(result['resource']['base64'],source()['base64']);self.assertEqual(result['resource']['archaeology']['legacyExcel']['reasonCode'],'XLS_BUSY');slots.release.assert_not_called()
 @unittest.skipUnless(os.name=='nt','Windows process-limit failure boundary')
 def test_required_limit_failure_kills_worker_before_temporary_source_cleanup(self):
  with patch('xls_import.subprocess.Popen') as popen,patch('xls_import.WindowsJob',side_effect=OSError('Required limit failed')):
   process=popen.return_value;process.poll.return_value=0;result=ingest({'source':source(),'options':{}});self.assertEqual(result['tables'],[]);self.assertEqual(result['resource']['archaeology']['legacyExcel']['reasonCode'],'XLS_LIMIT_UNAVAILABLE');process.kill.assert_called_once();process.communicate.assert_called_once()
