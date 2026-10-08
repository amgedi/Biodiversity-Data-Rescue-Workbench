"""Offline RO-Crate 1.3 graph/payload checks, without claiming full JSON-LD validation."""
import hashlib,re
from datetime import date
from pathlib import PurePosixPath
VERSION='1.3'
def check(document,files):
 findings=[];entities={}
 def error(code,detail):findings.append({'code':code,'severity':'Error','description':detail,'source':'https://www.researchobject.org/ro-crate/specification/1.3/','ruleVersion':VERSION})
 def types(e):return e.get('@type',[]) if isinstance(e.get('@type'),list) else [e.get('@type')]
 if not isinstance(document,dict):document={};error('RO-DOCUMENT','Metadata must be a JSON object.')
 graph=document.get('@graph',[])
 if document.get('@context')!='https://w3id.org/ro/crate/1.3/context':error('RO-CONTEXT','Metadata must identify the pinned 1.3 context.')
 if not isinstance(graph,list):graph=[];error('RO-GRAPH','@graph must be an array.')
 for entity in graph:
  if not isinstance(entity,dict):error('RO-ENTITY','Graph entities must be objects.');continue
  identifier=entity.get('@id')
  if not isinstance(identifier,str) or not identifier or not entity.get('@type'):error('RO-ENTITY','Every entity needs a string identifier and type.');continue
  if identifier in entities:error('RO-ID','Entity identifiers must be distinct.')
  entities[identifier]=entity
 descriptor=entities.get('ro-crate-metadata.json',{});root=entities.get('./',{})
 if 'CreativeWork' not in types(descriptor) or descriptor.get('about')!={'@id':'./'}:error('RO-DESCRIPTOR','Metadata descriptor must identify the root Dataset.')
 if descriptor.get('conformsTo')!={'@id':'https://w3id.org/ro/crate/1.3'}:error('RO-VERSION','Metadata descriptor must identify version 1.3.')
 if 'Dataset' not in types(root):error('RO-ROOT','The root must be a Dataset.')
 for key in ['name','description','license','datePublished']:
  if not root.get(key):error('RO-REQUIRED','Missing required root property: '+key)
 try:date.fromisoformat(root.get('datePublished',''))
 except (TypeError,ValueError):error('RO-DATE','This exporter requires a confirmed, valid ISO calendar date.')
 def references(value):
  if isinstance(value,list):
   for entry in value:yield from references(entry)
  elif isinstance(value,dict):
   if '@id' in value:yield value['@id']
   for k,v in value.items():
    if k!='@id':yield from references(v)
 for identifier,entity in entities.items():
  for key,value in entity.items():
   if key.startswith('@'):continue
   for ref in references(value):
    if not isinstance(ref,str):error('RO-REFERENCE','Referenced identifiers must be strings.');continue
    if not re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',ref) and ref not in entities:error('RO-REFERENCE','Local reference has no graph entity: '+ref)
  if 'File' in types(entity):
   path=PurePosixPath(identifier)
   if path.is_absolute() or '..' in path.parts or '\\' in identifier or ':' in identifier:error('RO-PATH','Payload File identifiers must use bounded relative paths: '+identifier);continue
   if identifier not in files:error('RO-PART','Payload file is absent: '+identifier);continue
   data=files[identifier]
   if entity.get('contentSize')!=str(len(data)):error('RO-FILE','Byte length differs from payload: '+identifier)
   checksum=entity.get('sha256')
   if not isinstance(checksum,str) or not re.fullmatch('[a-fA-F0-9]{64}',checksum) or checksum.lower()!=hashlib.sha256(data).hexdigest():error('RO-CHECKSUM','SHA-256 differs from payload: '+identifier)
 parts=root.get('hasPart',[]);parts=parts if isinstance(parts,list) else [parts]
 for part in parts:
  if not isinstance(part,dict) or not isinstance(part.get('@id'),str):error('RO-PART','hasPart entries must be identifier objects.');continue
  identifier=part['@id'];entity=entities.get(identifier,{})
  if identifier not in files or 'File' not in types(entity):error('RO-PART','Listed payload must exist and be typed File: '+identifier)
 for role in ['creator','contributor']:
  parties=root.get(role,[]);parties=parties if isinstance(parties,list) else [parties]
  for party in parties:
   identifier=party.get('@id') if isinstance(party,dict) else None
   if not isinstance(identifier,str) or identifier not in entities:error('RO-'+role.upper(),role.capitalize()+' references need a descriptive graph entity.');continue
   entity=entities[identifier]
   if not any(t in ['Person','Organization'] for t in types(entity)) or not isinstance(entity.get('name'),str) or not entity['name'].strip():error('RO-'+role.upper(),role.capitalize()+' entities require Person/Organization type and a recorded name.')
 action=entities.get('#workbench-export')
 if action is not None:
  if 'CreateAction' not in types(action):error('RO-PROVENANCE','Workbench export provenance must be typed CreateAction.')
  for key in ['object','result']:
   refs=action.get(key,[]);refs=refs if isinstance(refs,list) else [refs]
   if not refs or any(not isinstance(ref,dict) or not isinstance(ref.get('@id'),str) or ref['@id'] not in entities for ref in refs):error('RO-PROVENANCE','Workbench export '+key+' must reference included entities.')
  instrument=action.get('instrument',{});instrument_id=instrument.get('@id') if isinstance(instrument,dict) else None
  if not isinstance(instrument_id,str) or 'SoftwareApplication' not in types(entities.get(instrument_id,{})):error('RO-PROVENANCE','Workbench export must identify its software instrument.')
  try:
   from datetime import datetime
   datetime.fromisoformat(action.get('endTime','').replace('Z','+00:00'))
  except (AttributeError,TypeError,ValueError):error('RO-PROVENANCE','Workbench export requires a recorded ISO timestamp.')
 return {'standard':'RO-Crate','version':VERSION,'status':'Generated graph checks passed' if not findings else 'Generated graph has errors','findings':findings,'fullProfileValidated':False,'scientificallyValidated':False,'scope':'Pinned context/version, required root properties, publication date, identities/types, internal graph references, creator/contributor entities, Workbench export action/source/software links, bounded payload paths, byte lengths and SHA-256. Full JSON-LD expansion, external profile semantics and scientific completeness remain pending.'}
