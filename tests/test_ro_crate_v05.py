import io,json,unittest,zipfile
from exporters import export_v2
from ro_crate import check
from test_upgrade import sample
class CrateV05Tests(unittest.TestCase):
 def test_uploaded_crate_checks_actual_payload_and_rejects_corruption(self):
  from biodiversity_validation import validate_uploaded
  data=export_v2({'project':sample()});self.assertEqual(validate_uploaded(data,'preservation.zip')['findings'],[])
  with zipfile.ZipFile(io.BytesIO(data)) as archive:files={name:archive.read(name) for name in archive.namelist()}
  files['datapackage.json']=b'{}';stream=io.BytesIO()
  with zipfile.ZipFile(stream,'w') as archive:
   for name,content in files.items():archive.writestr(name,content)
  self.assertIn('RO-CHECKSUM',[f['code'] for f in validate_uploaded(stream.getvalue(),'changed.zip')['findings']])
 def exported(self,p=None):
  with zipfile.ZipFile(io.BytesIO(export_v2({'project':p or sample()}))) as archive:return {name:archive.read(name) for name in archive.namelist()}
 def test_version_root_entities_and_payload_lengths_are_checked(self):
  files=self.exported();document=json.loads(files['ro-crate-metadata.json']);result=json.loads(files['ro-crate-validation.json']);self.assertEqual(document['@context'],'https://w3id.org/ro/crate/1.3/context');self.assertEqual(result['findings'],[]);self.assertFalse(result['fullProfileValidated']);self.assertEqual(check(document,files)['findings'],[])
 def test_impossible_confirmed_date_blocks_generation_without_guessing(self):
  p=sample();p['metadata']['publicationDate']['value']='2026-02-30';files=self.exported(p);self.assertNotIn('ro-crate-metadata.json',files);self.assertFalse(json.loads(files['ro-crate-status.json'])['generated'])
 def test_broken_payload_and_duplicate_entities_are_reported(self):
  files=self.exported();document=json.loads(files['ro-crate-metadata.json']);document['@graph'].append(document['@graph'][0]);del files['datapackage.json'];codes=[x['code'] for x in check(document,files)['findings']];self.assertIn('RO-ID',codes);self.assertIn('RO-PART',codes)
 def test_changed_payload_bytes_are_detected_even_at_same_length(self):
  files=self.exported();document=json.loads(files['ro-crate-metadata.json']);path=next(x['@id'] for x in document['@graph'] if x.get('@type')=='File');files[path]=b'x'*len(files[path]);self.assertIn('RO-CHECKSUM',[x['code'] for x in check(document,files)['findings']])
 def test_missing_internal_creator_and_provenance_references_are_detected(self):
  files=self.exported();document=json.loads(files['ro-crate-metadata.json']);root=next(e for e in document['@graph'] if e['@id']=='./');root['creator']={'@id':'#missing'};root['isBasedOn']={'@id':'missing.csv'};codes=[x['code'] for x in check(document,files)['findings']];self.assertIn('RO-REFERENCE',codes);self.assertIn('RO-CREATOR',codes)
 def test_malformed_graph_types_return_findings_instead_of_crashing(self):
  for value in [[],{'@graph':{}},{'@graph':[None,{},{'@id':[],'@type':'File'}]}]:self.assertTrue(check(value,{})['findings'])

 def test_final_documentation_and_exact_source_provenance_are_in_graph(self):
  files=self.exported();document=json.loads(files['ro-crate-metadata.json']);entities={e['@id']:e for e in document['@graph']};root=entities['./']
  for path in ['README.txt','ARCHIVE_README.md','package-manifest.json','audit.json','recipe.json']:
   self.assertIn({'@id':path},root['hasPart']);self.assertEqual(entities[path]['sha256'],__import__('hashlib').sha256(files[path]).hexdigest())
  working=next(path for path in files if path.startswith('working/'));original=next(path for path in files if path.startswith('original/'))
  self.assertEqual(entities[working]['isBasedOn'],{'@id':original});action=entities['#workbench-export'];self.assertIn({'@id':working},action['result']);self.assertIn({'@id':original},action['object']);self.assertNotIn('agent',action);self.assertEqual(entities[action['instrument']['@id']]['@type'],'SoftwareApplication');self.assertEqual(check(document,files)['findings'],[])
 def test_malformed_contributors_and_workbench_action_produce_findings(self):
  files=self.exported();document=json.loads(files['ro-crate-metadata.json']);root=next(e for e in document['@graph'] if e['@id']=='./');root['contributor']={'@id':[]};action=next(e for e in document['@graph'] if e['@id']=='#workbench-export');action['instrument']={'@id':'#missing'};action['endTime']='not-a-date'
  codes=[f['code'] for f in check(document,files)['findings']];self.assertIn('RO-CONTRIBUTOR',codes);self.assertIn('RO-PROVENANCE',codes)

 def test_explicit_person_creator_and_contributor_export_without_invented_organization(self):
  p=sample();p['metadata'].pop('organizations');p['metadata']['creator'].update(value='Literal Person',partyType='Person',identifier='https://example.invalid/people/001');p['metadata']['contributors']={'value':'Recorded partner','status':'Confirmed','partyType':'Organization','identifier':'https://example.invalid/organizations/001'}
  files=self.exported(p);document=json.loads(files['ro-crate-metadata.json']);entities={e['@id']:e for e in document['@graph']};root=entities['./'];self.assertEqual(entities[root['creator']['@id']]['@type'],'Person');self.assertEqual(entities[root['contributor']['@id']]['name'],'Recorded partner');self.assertEqual(check(document,files)['findings'],[])
 def test_untyped_person_is_not_guessed_and_conflicting_identifiers_block_generation(self):
  p=sample();p['metadata'].pop('organizations');p['metadata']['creator']['value']='Potential person';files=self.exported(p);self.assertNotIn('ro-crate-metadata.json',files)
  p['metadata']['creator'].update(partyType='Person',identifier='https://example.invalid/id/001');p['metadata']['contributors']={'value':'Different person','status':'Confirmed','partyType':'Person','identifier':'https://example.invalid/id/001'};files=self.exported(p);self.assertIn('conflicting creator/contributor identifier',json.loads(files['ro-crate-status.json'])['missingConfirmedFields'])
 def test_invalid_party_types_and_relative_identifiers_are_rejected(self):
  from storage import validate
  for attrs in [{'partyType':'Guess'},{'partyType':[]},{'identifier':'../person'},{'identifier':'https://example.invalid/has whitespace'}]:
   p=sample();p['metadata']['creator'].update(attrs)
   with self.assertRaises(ValueError):validate(p)

 def test_explicit_unknown_type_remains_unknown_despite_legacy_matching_names(self):
  p=sample();p['metadata']['creator']['partyType']='Unknown';files=self.exported(p);self.assertNotIn('ro-crate-metadata.json',files);self.assertIn('confirmed explicit creator entity type',json.loads(files['ro-crate-status.json'])['missingConfirmedFields'])
