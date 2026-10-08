import tempfile,unittest
from pathlib import Path
from workspace_lock import WorkspaceLock
from edit_sessions import write_project_id
import test_editing_api
class WorkspaceLockTests(unittest.TestCase):
 def test_exclusive_workspace_can_reopen_after_clean_release(self):
  with tempfile.TemporaryDirectory() as temp:
   with WorkspaceLock(Path(temp)/'one'):
    with self.assertRaisesRegex(ValueError,'Another Workbench'):WorkspaceLock(Path(temp)/'one')
    with WorkspaceLock(Path(temp)/'two'):pass
   with WorkspaceLock(Path(temp)/'one'):pass
 def test_all_large_mutations_are_namespaced(self):
  for route in ['edit','chunk','start','cancel']:self.assertEqual(write_project_id('/api/large-'+route,{'id':'x'}),'large:x')
class LargeAuthorityTests(unittest.TestCase):
 setUp=test_editing_api.EditingApiTests.setUp
 tearDown=test_editing_api.EditingApiTests.tearDown
 call=test_editing_api.EditingApiTests.call
 def test_large_edit_authority_cannot_be_bypassed_by_anonymous_or_old_windows(self):
  job=self.server.large.create('tiny.csv',8)
  pid='large:'+job['id']
  status,owner=self.call('/api/edit-session',{'projectId':pid,'session':'window-one','action':'claim'});self.assertEqual(status,200,owner)
  _,next_owner=self.call('/api/edit-session',{'projectId':pid,'session':'window-two','action':'takeover','generation':owner['generation']})
  payload={'id':job['id'],'offset':0,'data':'YSxiCjEsMgo='}
  self.assertEqual(self.call('/api/large-chunk',payload)[0],400)
  self.assertEqual(self.call('/api/large-chunk',payload,owner)[0],400)
  self.assertEqual(self.call('/api/large-chunk',payload,next_owner)[0],200)
