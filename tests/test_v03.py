import base64,copy,io,json,tempfile,unittest,zipfile
from pathlib import Path
from test_upgrade import sample,source
from storage import Store
from upgrades import migrate,migration_preview,migrate_saved,snapshot,snapshots,open_snapshot,compare,save_draft,recovery_status,verify_package,safe_archive
from large_data import LargeStore
from importers import ingest
from exporters import export_v2
from validation_v3 import descriptor_validation,composite_checks
class V03Tests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name)/'store')
 def tearDown(self):self.temp.cleanup()
 def test_genuine_v02_fixture_migrates_without_losing_unknown_fields(self):
  p=json.loads((Path(__file__).parent/'fixtures/v02-project.json').read_text());p['unknownExtension']={'retained':[1,2,3]};n=migrate(p)
  self.assertEqual(n['projectSchemaVersion'],3);self.assertEqual(n['resources'],p['resources']);self.assertEqual(n['tables'],p['tables']);self.assertEqual(n['relationships'],p['relationships']);self.assertEqual(n['unknownExtension'],p['unknownExtension']);self.assertEqual(n['audit'][:-1],p['audit']);self.assertEqual(migrate(n),n)
 def test_migration_backup_is_saved_before_update(self):
  p=self.store.save(sample());n=migrate_saved(self.store,p);self.assertEqual(n['revision'],2);backup=list((self.store.root/'migrations'/p['id']).glob('*.json'))[0];self.assertEqual(json.loads(backup.read_text()),p);self.assertEqual(n['migrationHistory'][0]['from'],2)
 def test_future_schema_rejected_without_mutating(self):
  p=sample();p['projectSchemaVersion']=999;before=copy.deepcopy(p)
  with self.assertRaises(ValueError):migration_preview(p)
  self.assertEqual(p,before)
 def test_schema3_audit_and_evidence_cannot_be_rewritten(self):
  p=migrate(sample());p['evidenceAssertions']=[{'id':'a','value':'old'}];p=self.store.save(p);changed=copy.deepcopy(p);changed['evidenceAssertions'][0]['value']='rewritten'
  with self.assertRaises(ValueError):self.store.save(changed)
  changed=copy.deepcopy(p);changed['audit'][0]['reason']='rewritten'
  with self.assertRaises(ValueError):self.store.save(changed)
 def test_dbf_deleted_records_and_literal_units_retained(self):
  data=(Path(__file__).parent.parent/'examples/nightmare/sites.dbf').read_bytes();r=ingest({'source':source(data,'sites.dbf')});self.assertEqual(r['tables'][0]['rows'][1][1],'2500');self.assertEqual(r['tables'][0]['rows'][-1][-1],'true');self.assertIn('memo',r['resource']['archaeology']['notes'][0])
 def test_snapshots_do_not_embed_source_bytes_and_restore_checksums(self):
  p=self.store.save(migrate(sample()));result=snapshot(self.store,p,'Initial import');items=snapshots(self.store,p['id']);self.assertEqual(items[0]['name'],'Initial import');raw=json.loads((self.store.root/'snapshots'/p['id']/(result['snapshotId']+'.json')).read_text());self.assertNotIn('base64',raw['project']['resources'][0]);restored=open_snapshot(self.store,p['id'],result['snapshotId']);self.assertEqual(restored['resources'],p['resources'])
 def test_stale_snapshot_rejected(self):
  p=self.store.save(sample());self.store.save(p)
  with self.assertRaises(ValueError):snapshot(self.store,p,'stale')
 def test_literal_comparison_counts_duplicates_and_metadata_changes(self):
  p=sample();n=copy.deepcopy(p);n['tables'][0]['rows']*=2;n['metadata']['title']['value']='changed';r=compare(p,n);self.assertEqual(r['tables'][0]['addedRows'],1);self.assertTrue(r['metadataChanged'])
 def test_drafts_never_overwrite_newer_commit(self):
  p=self.store.save(sample());self.store.save(p);save_draft(self.store,{'projectId':p['id'],'baseRevision':1,'forms':{'metadata':{'value':'stale'}}});s=recovery_status(self.store,p['id']);self.assertTrue(s['draftStale']);self.assertEqual(self.store.get(p['id'])['revision'],2)
 def test_package_checksum_verification_detects_tampering_and_unlisted_files(self):
  data=export_v2({'project':sample()});self.assertTrue(verify_package(data)['valid']);out=io.BytesIO()
  with zipfile.ZipFile(io.BytesIO(data)) as old,zipfile.ZipFile(out,'w') as new:
   for name in old.namelist():new.writestr(name,b'changed' if name=='metadata.json' else old.read(name))
   new.writestr('secret.txt',b'unlisted')
  r=verify_package(out.getvalue());self.assertFalse(r['valid']);self.assertIn('secret.txt',r['unlisted'])
 def test_public_package_remains_verifiable_and_isolated(self):
  p=sample();data=export_v2({'project':p,'policy':{'mode':'redact'}});self.assertTrue(verify_package(data)['valid'])
  with zipfile.ZipFile(io.BytesIO(data)) as z:self.assertNotIn('rescue-report.html',z.namelist());self.assertNotIn('package-manifest.json',z.namelist())
 def test_archive_path_traversal_and_symlink_rejected(self):
  for name in ['../escape.csv','C:/bad.txt','a\\b.txt','/absolute']:
   out=io.BytesIO()
   with zipfile.ZipFile(out,'w') as z:z.writestr(name,b'x')
   data=out.getvalue()
   if name=='a'+chr(92)+'b.txt':data=data.replace(b'a/b.txt',b'a'+bytes([92])+b'b.txt')
   with self.assertRaises(ValueError):safe_archive(data)
 def test_decompression_bomb_rejected(self):
  out=io.BytesIO()
  with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('bomb.txt',b'0'*1024*1024)
  with self.assertRaises(ValueError):safe_archive(out.getvalue())
 def test_archive_inspection_does_not_extract(self):
  out=io.BytesIO()
  with zipfile.ZipFile(out,'w') as z:z.writestr('notes.txt',b'evidence')
  imported=ingest({'source':source(out.getvalue(),'project.zip')});self.assertEqual(imported['tables'],[]);self.assertEqual(imported['resource']['archaeology']['members'][0]['name'],'notes.txt')
 def test_geojson_preserves_geometry_and_foreign_context(self):
  v={'type':'FeatureCollection','note':'old CRS unknown','features':[{'type':'Feature','id':'01','properties':{'code':'RAPI'},'geometry':{'type':'Point','coordinates':[-113,53]}}]};r=ingest({'source':source(json.dumps(v).encode(),'a.geojson')});self.assertEqual(r['tables'][0]['rows'][0][0],'RAPI');self.assertIn('Point',r['tables'][0]['rows'][0][-1])
 def test_official_descriptor_schema_rejects_invalid_resources(self):
  r=descriptor_validation({'profile':'data-package','resources':'broken'});self.assertIn('errors',r);self.assertTrue(r['errors'])
 def test_official_descriptor_schema_validates_export(self):
  with zipfile.ZipFile(io.BytesIO(export_v2({'project':sample()}))) as z:r=json.loads(z.read('data-package-validation.json'));self.assertEqual(r['errors'],[],r['errors'])
 def test_report_escapes_malicious_metadata(self):
  p=sample();p['metadata']['title']['value']='<script>alert(1)</script>'
  with zipfile.ZipFile(io.BytesIO(export_v2({'project':p}))) as z:html=z.read('rescue-report.html').decode();self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)
 def test_composite_relationship_orphans_use_full_tuple(self):
  p=sample();a=p['tables'][0];a['headers']=['x','y','value'];a['rows']=[['1','A','0'],['1','B','0']];b=copy.deepcopy(a);b['id']='t2';b['rows']=[['1','A','0']];p['tables'].append(b);p['relationships']=[{'fromTable':'t1','toTable':'t2','fromFields':['x','y'],'toFields':['x','y']}];r=composite_checks(p);self.assertEqual(r[0]['rows'],[1])
class StreamingTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.large=LargeStore(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def import_data(self,data,name='test.csv',encoding='utf-8-sig',delimiter=','):
  j=self.large.create(name,len(data),encoding,delimiter)
  for i in range(0,len(data),1048576):self.large.chunk(j['id'],i,base64.b64encode(data[i:i+1048576]).decode())
  return self.large.start(j['id'],background=False)
 def test_200000_rows_chunked_profile_paging_filter_and_export(self):
  data=('id,note,n\n'+''.join(f'{i:07d},site {i%10},{i%100}\n' for i in range(200000))).encode();j=self.import_data(data);self.assertEqual(j['status'],'ready');self.assertEqual(j['rows'],200000);self.assertEqual(j['sha256'],__import__('hashlib').sha256(data).hexdigest());self.assertEqual(j['profile'][2]['numericMax'],99);page=self.large.page(j['id'],50);self.assertEqual(len(page['rows']),50);self.assertEqual(page['rows'][0]['values'][0],'0000050');self.assertEqual(self.large.page(j['id'],0,'site 3')['total'],20000);self.assertEqual(b''.join(self.large.export(j['id'])),data)
 def test_multiline_delimiters_bom_and_windows1252(self):
  j=self.import_data('id;note\n01;"forêt;\nmore"\n'.encode('cp1252'),encoding='cp1252',delimiter=';');self.assertEqual(self.large.page(j['id'])['rows'][0]['values'][1],'forêt;\nmore')
 def test_broken_encoding_and_ragged_csv_preserve_original(self):
  for data in [b'id,name\n01,\xff\n',b'id,name\n01\n',b'id,name\n01,"bad']:
   j=self.import_data(data);self.assertEqual(j['status'],'failed');self.assertEqual((self.large.folder(j['id'])/'original.bin').read_bytes(),data)
 def test_cancellation_does_not_publish_incomplete_table(self):
  data=b'id,n\n01,0\n';j=self.large.create('a.csv',len(data));self.large.chunk(j['id'],0,base64.b64encode(data).decode());self.large.cancel(j['id']);self.assertEqual(self.large.status(j['id'])['status'],'cancelled')
  with self.assertRaises(ValueError):self.large.page(j['id'])
 def test_offset_conflict_and_size_limit(self):
  j=self.large.create('a.csv',10)
  with self.assertRaises(ValueError):self.large.chunk(j['id'],2,base64.b64encode(b'x').decode())
  with self.assertRaises(ValueError):self.large.create('too.csv',300*1024*1024)
 def test_server_restart_marks_incomplete_import(self):
  j=self.large.create('a.csv',10);other=LargeStore(self.temp.name);self.assertEqual(other.status(j['id'])['status'],'interrupted')
