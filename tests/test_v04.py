import base64,csv,io,json,sqlite3,tempfile,threading,unittest,zipfile,hashlib
from pathlib import Path
from unittest.mock import patch
from large_data import LargeStore
from biodiversity_validation import camtrap_tables,camtrap_descriptor,eml_validate,validate_uploaded
from exporters import eml_draft
from test_upgrade import sample
ROOT=Path(__file__).resolve().parent.parent
class LargeEditTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.store=LargeStore(self.temp.name);self.raw=b'id,note,n\n001,"quoted, value",0\n002,"multi\nline",NA\n003,same,same\n';self.id=self.import_csv(self.raw)
 def tearDown(self):self.temp.cleanup()
 def import_csv(self,data):
  j=self.store.create('fixture.csv',len(data));self.store.chunk(j['id'],0,base64.b64encode(data).decode());self.store.start(j['id'],False);return j['id']
 def edit(self,**changes):
  args=dict(id=self.id,revision=self.store.edit_state(self.id)['revision'],row=2,column=2,value='4',expected='NA',reason='Fixture notebook review');args.update(changes);return self.store.edit(**args)
 def test_edit_export_original_and_restart(self):
  before=self.store.page(self.id)['rows'];self.edit();after=self.store.page(self.id)['rows'];self.assertEqual(before[0],after[0]);self.assertEqual(before[2],after[2]);self.assertEqual(after[1]['values'],['002','multi\nline','4']);self.assertEqual((self.store.folder(self.id)/'original.bin').read_bytes(),self.raw);self.assertEqual(LargeStore(self.temp.name).edit_state(self.id)['revision'],1);self.assertEqual(list(csv.reader(io.StringIO(b''.join(self.store.export(self.id)).decode())))[2],['002','multi\nline','4'])
 def test_undo_redo_branch_retains_append_only_history(self):
  self.edit();self.edit(action='undo');self.edit(action='redo');self.edit(action='undo');self.edit(value='5');state=self.store.edit_state(self.id);self.assertFalse(state['canRedo']);history=[json.loads(x) for x in self.store.history(self.id)];self.assertEqual([h['action'] for h in history],['edit','undo','redo','undo','edit']);self.assertEqual(history[0]['after'],'4');self.assertEqual(history[-1]['after'],'5')
 def test_conflicts_and_invalid_changes_never_modify(self):
  for change in [dict(revision=5),dict(expected='different'),dict(row=-1),dict(column=10),dict(reason=''),dict(value='NA')]:
   with self.assertRaises(ValueError):self.edit(**change)
  self.assertEqual(self.store.edit_state(self.id)['revision'],0);self.assertEqual(list(self.store.history(self.id)),[])
 def test_transaction_failure_rolls_back_value_and_history(self):
  conn=self.store.edit_connection(self.id);conn.execute("CREATE TRIGGER fail_history BEFORE INSERT ON edit_history BEGIN SELECT RAISE(ABORT,'simulated interrupted transaction'); END");conn.commit();conn.close()
  with self.assertRaises(sqlite3.IntegrityError):self.edit()
  self.assertEqual(self.store.page(self.id)['rows'][1]['values'][2],'NA');self.assertEqual(self.store.edit_state(self.id)['revision'],0)
 def test_two_store_instances_cannot_overwrite_stale_revision(self):
  other=LargeStore(self.temp.name);results=[]
  def write(store,value):
   try:store.edit(self.id,0,2,2,value,'NA','Concurrent fixture review');results.append('saved')
   except ValueError:results.append('conflict')
  ts=[threading.Thread(target=write,args=(store,value)) for store,value in [(self.store,'4'),(other,'5')]]
  for t in ts:t.start()
  for t in ts:t.join()
  self.assertCountEqual(results,['saved','conflict']);self.assertEqual(self.store.edit_state(self.id)['revision'],1)
 def test_export_is_consistent_while_editing(self):
  raw=('id,note\n'+''.join(f'{i:06d},'+('x'*100)+'\n' for i in range(2000))).encode();id=self.import_csv(raw);stream=self.store.export(id);out=[next(stream),next(stream)];self.store.edit(id,0,1800,1,'changed','x'*100,'Concurrent export fixture');out+=list(stream);rows=list(csv.reader(io.StringIO(b''.join(out).decode())));self.assertEqual(rows[1800][1],'x'*100);self.assertIn(b'changed',b''.join(self.store.export(id)))
 def test_v03_large_database_is_backed_up_before_upgrade(self):
  self.store.jobs[self.id].pop('storageVersion',None);self.store.edit_state(self.id);backup=self.store.folder(self.id)/'pre-v04-rows.sqlite';self.assertTrue(backup.exists());conn=sqlite3.connect(backup);self.assertFalse(conn.execute("SELECT 1 FROM sqlite_master WHERE name='edit_meta'").fetchone());self.assertEqual(conn.execute('SELECT count(*) FROM rows').fetchone()[0],3);conn.close();self.edit();conn=sqlite3.connect(backup);self.assertEqual(json.loads(conn.execute('SELECT data FROM rows WHERE id=2').fetchone()[0])[2],'NA');conn.close()
 def test_variable_page_size_and_special_literal_search(self):
  self.assertEqual(len(self.store.page(self.id,limit=1)['rows']),1);self.assertEqual(self.store.page(self.id,query='multi\nline')['total'],1)
  with self.assertRaises(ValueError):self.store.page(self.id,limit=101)
 def test_interrupted_upload_reports_actual_preserved_bytes(self):
  j=self.store.create('partial.csv',100);self.store.chunk(j['id'],0,base64.b64encode(b'a,b\n').decode());other=LargeStore(self.temp.name);state=other.status(j['id']);self.assertEqual(state['status'],'interrupted');self.assertEqual(state['receivedBytes'],4)
class BiodiversityValidationTests(unittest.TestCase):
 def setUp(self):
  self.folder=ROOT/'tests/fixtures/camtrap-1.0.2';self.descriptor=json.loads((self.folder/'datapackage.json').read_text());self.tables=[]
  for name in ['deployments','media','observations']:
   rows=list(csv.reader(io.StringIO((self.folder/(name+'.csv')).read_text(encoding='utf-8'))));self.tables.append({'name':name,'headers':rows[0],'rows':rows[1:]})
 def test_official_camtrap_table_fixture_and_no_outbound_requests(self):
  with patch('socket.create_connection',side_effect=AssertionError('Network forbidden')):r=camtrap_tables(self.tables)
  self.assertEqual(r['findings'],[]);self.assertGreater(r['recordsChecked'],0);self.assertFalse(r['scientificallyValidated'])
 def test_descriptor_reports_pinned_base_role_compatibility(self):
  r=camtrap_descriptor(self.descriptor);self.assertEqual(len(r['findings']),3);self.assertTrue(all('role' in x['path'] for x in r['findings']))
  for c in self.descriptor['contributors']:c.pop('role',None)
  with patch('socket.create_connection',side_effect=AssertionError('Network forbidden')):r=camtrap_descriptor(self.descriptor)
  self.assertEqual(r['findings'],[])
 def test_camtrap_errors_cover_types_vocab_ranges_and_references(self):
  t=self.tables[0];t['rows'][0][t['headers'].index('latitude')]='999';t=self.tables[2];t['rows'][0][t['headers'].index('observationType')]='invented';t['rows'][0][t['headers'].index('deploymentID')]='missing';t['rows'][0][t['headers'].index('count')]='abc';before=json.dumps(self.tables);r=camtrap_tables(self.tables);codes={f['code'] for f in r['findings']};self.assertTrue({'CAMTRAP-MAXIMUM','CAMTRAP-VOCABULARY','CAMTRAP-FOREIGN-KEY','CAMTRAP-TYPE'}<=codes);self.assertEqual(json.dumps(self.tables),before)
 def test_eml_full_xsd_valid_invalid_and_entities(self):
  data,status=eml_draft(sample());self.assertTrue(status['xsdValidated']);self.assertTrue(eml_validate(data)['xsdValidated']);broken=data.replace(b'<title>',b'<bad>').replace(b'</title>',b'</bad>');self.assertFalse(eml_validate(broken)['xsdValidated'])
  for data in [b'<!DOCTYPE eml [<!ENTITY x SYSTEM "file:///secret">]><eml>&x;</eml>','<!DOCTYPE eml><eml/>'.encode('utf-16')]:
   with self.assertRaises(ValueError):eml_validate(data)
 def test_uploaded_package_checks_preserved_local_tables(self):
  r=validate_uploaded((ROOT/'examples/camtrap-official-example.zip').read_bytes(),'official.zip');self.assertEqual(len(r['findings']),3);self.assertEqual(r['version'],'1.0.2')
 def test_missing_optional_validator_is_not_reported_as_pass(self):
  import sys
  with patch.dict(sys.modules,{'jsonschema':None}):r=validate_uploaded((ROOT/'examples/camtrap-official-example.zip').read_bytes(),'official.zip')
  self.assertIn('Unavailable',r['status']);self.assertEqual(r['descriptor']['status'],'Unavailable')
 def test_external_package_resources_are_not_fetched(self):
  self.descriptor['resources'][0]['path']='https://example.invalid/data.csv';buf=io.BytesIO()
  with zipfile.ZipFile(buf,'w') as z:z.writestr('datapackage.json',json.dumps(self.descriptor))
  with self.assertRaisesRegex(ValueError,'external URLs'):validate_uploaded(buf.getvalue(),'a.zip')
 def test_malformed_descriptors_and_empty_tables_are_clear_errors(self):
  for descriptor in [[],{'profile':[],'resources':[]},{'profile':'camtrap','resources':{}},{'profile':'camtrap','resources':[{'name':'deployments','path':'deployments.csv'}]}]:
   buf=io.BytesIO()
   with zipfile.ZipFile(buf,'w') as z:
    z.writestr('datapackage.json',json.dumps(descriptor))
    if isinstance(descriptor,dict) and isinstance(descriptor.get('resources'),list):
     for resource in descriptor['resources']:z.writestr(resource['path'],'')
   with self.assertRaises(ValueError):validate_uploaded(buf.getvalue(),'malformed.zip')

class ArchiveV04Tests(unittest.TestCase):
 def test_actual_symlink_entry_is_rejected(self):
  from upgrades import safe_archive
  import stat
  entry=zipfile.ZipInfo('data.csv');entry.create_system=3;entry.external_attr=(stat.S_IFLNK|0o777)<<16;buf=io.BytesIO()
  with zipfile.ZipFile(buf,'w') as z:z.writestr(entry,'outside.csv')
  with self.assertRaises(ValueError):safe_archive(buf.getvalue())
