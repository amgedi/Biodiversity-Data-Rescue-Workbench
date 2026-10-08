"""Pinned offline schema providers. Review status never becomes ratified by inference."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent/'vendor/biodiversity/dwc-dp-review'
class SchemaProvider:
 def __init__(self,root=ROOT):
  self.root=Path(root);self.metadata=json.loads((self.root/'provider.json').read_text(encoding='utf-8'))
  for record in self.metadata['files']:
   if hashlib.sha256((self.root/record['path']).read_bytes()).hexdigest()!=record['sha256']:raise ValueError('DwC-DP schema provider integrity mismatch: '+record['path'])
  self.profile=json.loads((self.root/'dwc-dp-profile.json').read_text(encoding='utf-8'));self.tables={p.stem:json.loads(p.read_text(encoding='utf-8')) for p in (self.root/'table-schemas').glob('*.json')}
 def summary(self):return {k:v for k,v in self.metadata.items() if k!='files'}
 def table(self,name):return self.tables.get(name)
 def reserved(self):return set(self.profile['$defs']['dwc-dp-resource-names']['enum'])
def provider(provider_id=None):
 if provider_id is None:return None
 if provider_id!='tdwg-review-2026-07':raise ValueError('Unknown offline DwC-DP provider.')
 return SchemaProvider()
