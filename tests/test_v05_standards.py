import io,json,unittest,zipfile,gzip
from dwc_dp import PROFILE,preflight,capability
from biodiversity_validation import validate_uploaded
class GuidePreflightTests(unittest.TestCase):
 def package(self,change=None,data=b'eventID\nE1\n',path='event.csv'):
  d={'profile':PROFILE,'resources':[{'name':'event','path':path,'profile':'tabular-data-resource','format':'csv','mediatype':'text/csv','schema':{'fields':[{'name':'eventID','title':'Event ID','description':'An identifier for an event.','type':'string','dcterms:isVersionOf':'http://rs.tdwg.org/dwc/terms/eventID'}],'primaryKey':['eventID']}}]}
  if change:change(d)
  stream=io.BytesIO()
  with zipfile.ZipFile(stream,'w') as z:z.writestr('datapackage.json',json.dumps(d));z.writestr(path,data)
  return stream.getvalue()
 def test_guide_valid_package_never_claims_official_conformance(self):
  result=validate_uploaded(self.package(),'guide.zip');self.assertTrue(result['guidePreflightPassed']);self.assertFalse(result['officialSchemasValidated']);self.assertFalse(result['scientificallyValidated']);self.assertIn('Blocked externally',result['formalConformanceStatus']);self.assertEqual(result['recordsRead'],{'event':1})
 def test_external_schema_and_missing_term_are_reported(self):
  result=validate_uploaded(self.package(lambda d:d['resources'][0].update(schema='https://example.invalid/schema')),'guide.zip');self.assertFalse(result['guidePreflightPassed']);self.assertIn('DWC-DP-INLINE-SCHEMA',[x['code'] for x in result['findings']])
  result=validate_uploaded(self.package(lambda d:d['resources'][0]['schema']['fields'][0].pop('dcterms:isVersionOf')),'guide.zip');self.assertIn('DWC-DP-TERM-IRI',[x['code'] for x in result['findings']])
 def test_undeclared_encoding_and_bad_record_width_are_errors(self):
  for raw in [b'eventID\n\xff\n',b'eventID\nE1,extra\n']:
   self.assertFalse(validate_uploaded(self.package(data=raw),'guide.zip')['guidePreflightPassed'])
 def test_optional_predicate_is_allowed_and_header_difference_is_error(self):
  result=validate_uploaded(self.package(lambda d:d['resources'][0]['schema'].update(foreignKeys=[{'fields':'eventID','reference':{'resource':'event','fields':'eventID'}}]),data=b'wrong\nE1\n'),'guide.zip');codes=[x['code'] for x in result['findings']];self.assertNotIn('DWC-DP-PREDICATE',codes);self.assertIn('DWC-DP-HEADER',codes)
 def test_gzip_resource_reads_and_retains_literal_records(self):
  result=validate_uploaded(self.package(data=gzip.compress(b'eventID\n001\n'),path='event.csv.gz'),'guide.zip');self.assertTrue(result['guidePreflightPassed']);self.assertEqual(result['recordsRead']['event'],1)
 def test_official_blocker_is_explicit_and_network_free(self):
  self.assertEqual(capability()['targetVersion'],'1.0');self.assertFalse(capability()['conformanceAvailable']);self.assertFalse(capability()['runtimeNetwork'])
