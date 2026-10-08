import unittest
from migration_registry import Migration, MigrationRegistry
from upgrades import migrate,migration_preview
from test_v03 import sample

class RegistryTests(unittest.TestCase):
 def test_ordered_fixture_steps_and_idempotence(self):
  calls=[]
  def step(target):
   def apply(p,c):calls.append(target);p['projectSchemaVersion']=target;p.setdefault('history',[]).append(target)
   return apply
  registry=MigrationRegistry([Migration(3,4,'third','third',step(4)),Migration(2,3,'second','second',step(3))],4)
  original={'unknown':{'literal':'001'},'projectSchemaVersion':2}
  result=registry.migrate(original,{})
  self.assertEqual(calls,[3,4]);self.assertEqual(result['unknown'],original['unknown']);self.assertNotIn('history',original)
  self.assertEqual(registry.migrate(result,{}),result);self.assertEqual(calls,[3,4])
 def test_failed_step_never_changes_input(self):
  def fail(p,c):p['unknown']='changed';raise RuntimeError('fixture failure')
  registry=MigrationRegistry([Migration(2,3,'failing','failure',fail)],3);p={'unknown':'original'}
  with self.assertRaisesRegex(ValueError,'failing failed; original'):registry.migrate(p,{})
  self.assertEqual(p,{'unknown':'original'})
 def test_gaps_duplicates_and_future_versions_refused(self):
  step=Migration(2,3,'a','a',lambda p,c:None)
  for steps,current in [([],3),([step,step],3),([step],4)]:
   with self.assertRaises(ValueError):MigrationRegistry(steps,current)
  for version in [4,True,'3',1]:
   with self.assertRaises(ValueError):MigrationRegistry([step],3).path(version)
 def test_actual_plan_matches_stable_step_and_preserves_fixture(self):
  p=sample();p['unknownExtension']={'literal':'0','missing':'NA'}
  plan=migration_preview(p);self.assertEqual(plan['steps'],[{'id':'schema-2-to-3-evidence-recovery','from':2,'to':3}])
  n=migrate(p);self.assertEqual(n['resources'],p['resources']);self.assertEqual(n['unknownExtension'],p['unknownExtension']);self.assertEqual(migrate(n),n)
