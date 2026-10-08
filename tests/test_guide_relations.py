import io,json,unittest,zipfile
import test_v05_standards
from biodiversity_validation import validate_uploaded
from schema_providers import provider
class GuideRelationsTests(unittest.TestCase):
 package=test_v05_standards.GuidePreflightTests.package
 def test_tsv_and_headerless_resources_keep_literal_identifiers(self):
  for data,dialect in [(b'eventID\n001\n',{'delimiter':'\t'}),(b'001\n',{'delimiter':'\t','header':False})]:
   result=validate_uploaded(self.package(lambda d:d['resources'][0].update(format='tsv',dialect=dialect),data),'guide.zip');self.assertTrue(result['guidePreflightPassed']);self.assertEqual(result['recordsRead'],{'event':1})
 def test_null_and_duplicate_keys_are_flagged(self):
  result=validate_uploaded(self.package(data=b'eventID\n001\n001\n""\n'),'guide.zip');codes=[x['code'] for x in result['findings']];self.assertIn('DWC-DP-PRIMARY-DUPLICATE',codes);self.assertIn('DWC-DP-PRIMARY-NULL',codes)
 def test_self_reference_requires_declared_primary_key_and_actual_parent(self):
  def modify(d):d['resources'][0]['schema']['foreignKeys']=[{'fields':'eventID','reference':{'resource':'','fields':'eventID'}}]
  self.assertTrue(validate_uploaded(self.package(modify),'guide.zip')['guidePreflightPassed'])
  def bad(d):modify(d);d['resources'][0]['schema'].pop('primaryKey')
  self.assertIn('DWC-DP-FOREIGN-TARGET',[f['code'] for f in validate_uploaded(self.package(bad),'guide.zip')['findings']])
 def test_required_field_documentation_is_not_silently_accepted(self):
  result=validate_uploaded(self.package(lambda d:d['resources'][0]['schema']['fields'][0].pop('description')),'guide.zip');self.assertIn('DWC-DP-FIELD-DESCRIPTION',[f['code'] for f in result['findings']])
 def test_pinned_review_provider_is_explicit_and_never_ratified(self):
  review=provider('tdwg-review-2026-07');self.assertFalse(review.metadata['ratified']);self.assertGreater(len(review.tables),70)
  def modify(d):d['resources'][0]['schema'].update(fields=[next(f for f in review.table('event')['fields'] if f['name']==name) for name in ['event_pk','eventCategory']],primaryKey='event_pk')
  result=validate_uploaded(self.package(modify,data=b'event_pk,eventCategory\n001,survey\n'),'guide.zip','tdwg-review-2026-07');self.assertTrue(result['guidePreflightPassed']);self.assertTrue(result['reviewSchemasChecked']);self.assertFalse(result['officialSchemasValidated']);self.assertEqual(result['provider']['commit'],'0fc041559db078c0c1cbdba8f8ffb4073319e2fa')
 def test_review_descriptor_mismatch_is_not_guide_conformance_claim(self):
  result=validate_uploaded(self.package(),'guide.zip','tdwg-review-2026-07');self.assertIn('DWC-DP-REVIEW-DESCRIPTOR',[f['code'] for f in result['findings']]);self.assertFalse(result['guidePreflightPassed'])

