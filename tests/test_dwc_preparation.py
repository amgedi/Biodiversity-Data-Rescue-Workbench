import copy,io,json,unittest,zipfile
from test_upgrade import sample
from dwc_preparation import prepare,export
class PreparationTests(unittest.TestCase):
 def test_full_term_iris_are_not_double_prefixed(self):
  payload=self.payload()
  for field in payload['project']['tables'][0]['columns']:field['term']='http://rs.tdwg.org/dwc/terms/'+field['term']
  _,report,_=prepare(payload);self.assertTrue(report['preparationReady'],report['findings'])
 def payload(self):
  p=sample();t=p['tables'][0];t['headers'].append('category');t['rows'][0].append('survey');t['columns'].append({'workingName':'category','description':'Confirmed fixture category','dataType':'string','status':'Confirmed','term':'eventCategory'});p['tables'][0]['columns'][0].update(term='eventID',status='Confirmed');return {'project':p,'schemaProvider':'tdwg-review-2026-07','mappings':[{'tableId':'t1','tableName':'event','fields':['event_pk','decimalLatitude','decimalLongitude','eventCategory']}]}
 def test_explicit_review_preparation_preserves_literal_rows_and_records_provider(self):
  payload=self.payload();before=copy.deepcopy(payload['project']);descriptor,report,files=prepare(payload);self.assertTrue(report['preparationReady'],report['findings']);self.assertEqual(payload['project'],before);self.assertFalse(report['officialSchemasValidated']);self.assertIn(b'001,53.54123,-113.4978',files['event.csv']);self.assertFalse(descriptor['biorescue:schemaProvider']['ratified']);self.assertEqual(json.loads(files['preparation-provenance.json'])['projectId'],'p1')
  with zipfile.ZipFile(io.BytesIO(export(payload))) as z:self.assertIn('checksums.sha256',z.namelist());self.assertIn('guide-validation.json',z.namelist())
 def test_unconfirmed_or_wrong_term_cannot_export(self):
  payload=self.payload();payload['project']['tables'][0]['columns'][0]['status']='Inferred';_,report,_=prepare(payload);self.assertFalse(report['preparationReady'])
  with self.assertRaisesRegex(ValueError,'unresolved'):export(payload)
 def test_missing_table_mapping_is_never_silent_omission(self):
  payload=self.payload();payload['mappings']=[]
  with self.assertRaisesRegex(ValueError,'every source table'):prepare(payload)
 def test_unknown_provider_and_duplicate_target_fields_are_rejected(self):
  payload=self.payload();payload['schemaProvider']='unreviewed'
  with self.assertRaisesRegex(ValueError,'Unknown'):prepare(payload)
  payload=self.payload();payload['mappings'][0]['fields']=['event_pk','decimalLatitude','decimalLatitude','eventCategory'];_,r,_=prepare(payload);self.assertFalse(r['preparationReady']);self.assertIn('DWC-PREP-DUPLICATE-FIELD',[f['code'] for f in r['findings']])
 def test_primary_key_and_orphan_relations_require_review(self):
  payload=self.payload();payload['mappings'][0]['fields'][0]='eventID';_,r,_=prepare(payload);self.assertFalse(r['preparationReady']);self.assertIn('DWC-PREP-PRIMARY',[f['code'] for f in r['findings']])
