import io,json,tempfile,unittest,zipfile
from storage import Store
from workspace_state import save
from exporters import export_v2
from upgrades import APP_VERSION
from test_upgrade import sample

class AnnotationExportTests(unittest.TestCase):
 def test_private_working_notes_are_absent_from_scientific_preservation_export(self):
  with tempfile.TemporaryDirectory() as folder:
   store=Store(folder);p=sample();store.save(p)
   save(store,{'projectId':p['id'],'revision':0,'action':'notes','value':[{'id':'note-1','text':'PRIVATE_WORKING_NOTE_NOT_SCIENTIFIC_METADATA'}]})
   before=store.path(p['id']).read_bytes()
   with zipfile.ZipFile(io.BytesIO(export_v2({'project':p,'policy':{'mode':'private'},'strict':False}))) as archive:
    self.assertFalse(any('workspace-state' in name for name in archive.namelist()))
    for name in archive.namelist():self.assertNotIn(b'PRIVATE_WORKING_NOTE_NOT_SCIENTIFIC_METADATA',archive.read(name))
    manifest=json.loads(archive.read('package-manifest.json'));recipe=json.loads(archive.read('recipe.json'))
    self.assertEqual(manifest['applicationVersion'],APP_VERSION)
    self.assertEqual(recipe['applicationVersion'],APP_VERSION)
    self.assertEqual(recipe['sources'][0]['bytes'],p['resources'][0]['bytes'])
    self.assertEqual(recipe['tableDefinitions'][0]['expectedOriginalHeaders'],p['tables'][0]['originalTable']['headers'])
   self.assertEqual(store.path(p['id']).read_bytes(),before)
