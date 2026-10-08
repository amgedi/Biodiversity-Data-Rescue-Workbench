import copy,io,json,unittest,zipfile
from dwc_dp import preflight,PROFILE
import test_dwc_preparation
from dwc_preparation import prepare
class GuideIntegrityTests(unittest.TestCase):
 def check(self,descriptor,files):
  stream=io.BytesIO()
  with zipfile.ZipFile(stream,'w') as archive:
   archive.writestr('datapackage.json',json.dumps(descriptor))
   for name,data in files.items():
    if name!='datapackage.json':archive.writestr(name,data)
  with zipfile.ZipFile(io.BytesIO(stream.getvalue())) as archive:return preflight(archive,descriptor)
 def prepared(self):return prepare(test_dwc_preparation.PreparationTests().payload())
 def test_same_length_valid_csv_tampering_is_detected_by_declared_sha256(self):
  descriptor,_,files=self.prepared();files['event.csv']=files['event.csv'].replace(b'001,',b'002,');report=self.check(descriptor,files);self.assertFalse(report['guidePreflightPassed']);self.assertIn('DWC-DP-HASH',[f['code'] for f in report['findings']])
 def test_declared_length_and_unsupported_hash_format_are_explained(self):
  descriptor,_,files=self.prepared();descriptor['resources'][0]['bytes']+=1;descriptor['resources'][0]['hash']='md5:unverified';report=self.check(descriptor,files);codes=[f['code'] for f in report['findings']];self.assertIn('DWC-DP-BYTES',codes);self.assertIn('DWC-DP-HASH-UNSUPPORTED',codes)
 def test_late_errors_after_500_warnings_still_fail_and_counts_are_complete(self):
  descriptor={'profile':PROFILE,'resources':[{'name':'event','path':'event.csv','profile':'tabular-data-resource','mediatype':'text/csv','schema':{'fields':[{'name':'id','title':'Literal ID','description':'Recorded literal','type':'unsupported','dcterms:isVersionOf':'http://rs.tdwg.org/dwc/terms/eventID'}]}},{'name':'notes','path':'notes.txt','profile':'data-resource','bytes':0}]};files={'event.csv':b'id\n'+b'001\n'*501,'notes.txt':b'context'};report=self.check(descriptor,files);self.assertFalse(report['guidePreflightPassed']);self.assertFalse(report['findingsComplete']);self.assertEqual(report['findingCountsBySeverity']['Error'],1);self.assertGreaterEqual(report['findingCountsBySeverity']['Warning'],501);self.assertGreater(report['omittedFindings'],0);self.assertEqual(report['findings'][-1]['code'],'DWC-DP-FINDINGS-TRUNCATED')

 def test_preparation_cannot_override_a_failed_check_when_error_details_are_capped(self):
  from unittest.mock import patch
  payload=test_dwc_preparation.PreparationTests().payload();_,report,_=prepare(payload);report.update(guidePreflightPassed=False,findings=[{'severity':'Warning','code':'TRUNCATED-FIXTURE','description':'Fixture with capped details'}],findingCountsBySeverity={'Error':1,'Warning':501},omittedFindings=2,findingsComplete=False)
  with patch('dwc_preparation.preflight',return_value=report):
   _,result,_=prepare(payload);self.assertFalse(result['preparationReady']);self.assertEqual(result['findingCountsBySeverity']['Error'],1)
