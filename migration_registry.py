"""Ordered, explicit migrations. Registry failures never mutate the caller."""
import copy
from dataclasses import dataclass

@dataclass(frozen=True)
class Migration:
    source: int
    target: int
    identity: str
    description: str
    apply: object

class MigrationRegistry:
    def __init__(self, steps, current, minimum=2):
        self.current=current; self.minimum=minimum; self.steps={}
        identities=set()
        for step in steps:
            if step.target!=step.source+1 or step.source in self.steps or step.identity in identities or not callable(step.apply):
                raise ValueError('Invalid or duplicate migration registration.')
            self.steps[step.source]=step;identities.add(step.identity)
        if set(self.steps)!=set(range(minimum,current)):
            raise ValueError('Migration registry has a missing or out-of-range step.')

    def path(self, version):
        if type(version) is not int:raise ValueError('Invalid project schema identity; original retained.')
        if version>self.current:raise ValueError('This project uses a newer schema. Keep the original backup and open with a compatible Workbench; no fields were discarded.')
        if version<self.minimum:raise ValueError('Use the legacy browser migration before schema migration.')
        return [self.steps[v] for v in range(version,self.current)]

    def migrate(self, project, context):
        result=copy.deepcopy(project)
        for step in self.path(project.get('projectSchemaVersion',2)):
            try:
                step.apply(result,context)
                if result.get('projectSchemaVersion')!=step.target:raise ValueError('Step did not establish its target schema.')
            except Exception as exc:
                raise ValueError(f'Migration {step.identity} failed; original project and pre-migration backup retained.') from exc
        return result
