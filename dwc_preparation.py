"""Explicit preparation from a pinned review provider, independent of ratified conformance."""
import copy,io,json,zipfile,hashlib
from datetime import datetime,timezone
from schema_providers import provider
from dwc_dp import PROFILE,preflight,key_fields
from rescue import csv_bytes
from storage import validate
from upgrades import APP_VERSION

def choices():
 p=provider('tdwg-review-2026-07')
 return {'provider':p.summary(),'tables':[{'name':name,'title':s.get('title',name),'fields':s['fields'],'primaryKey':s.get('primaryKey'),'foreignKeys':s.get('foreignKeys',[])} for name,s in sorted(p.tables.items())]}
def prepare(payload):
 project=validate(payload['project']);review=provider(payload.get('schemaProvider'));findings=[];files={};resources=[];selected={};mapping=payload.get('mappings',[])
 if review is None:raise ValueError('Explicitly select the pinned review provider; it is not a ratified schema release.')
 if not isinstance(mapping,list):raise ValueError('Table mappings must be a list.')
 ids={t['id'] for t in project['tables']}
 if {m.get('tableId') for m in mapping if isinstance(m,dict)}!=ids or len(mapping)!=len(ids):raise ValueError('Review one explicit mapping for every source table; no table is silently omitted.')
 def add(code,detail,**where):findings.append(dict(code=code,severity='Error',description=detail,**where))
 for m in mapping:
  table=next(t for t in project['tables'] if t['id']==m['tableId']);name=m.get('tableName');official=review.table(name) if isinstance(name,str) else None
  if not official:add('DWC-PREP-TABLE','Choose a review-provider table identity.',table=table['name']);continue
  if name in selected:add('DWC-PREP-DUPLICATE-TABLE','Two source tables cannot silently merge into one reserved table.',table=name);continue
  fields=m.get('fields',[]);official_fields={f['name']:f for f in official['fields']}
  if not isinstance(fields,list) or len(fields)!=len(table['headers']) or any(not isinstance(f,str) or f not in official_fields for f in fields):add('DWC-PREP-FIELDS','Explicitly select a review field for every source column.',table=name);continue
  if len(set(fields))!=len(fields):add('DWC-PREP-DUPLICATE-FIELD','Distinct source columns cannot silently overwrite one target field.',table=name);continue
  for column,target in zip(table['columns'],fields):
   term=column.get('term','');iri=term if term.startswith(('http://','https://')) else 'http://rs.tdwg.org/dwc/terms/'+term
   if column.get('status')!='Confirmed' or not term or official_fields[target]['dcterms:isVersionOf']!=iri:add('DWC-PREP-EVIDENCE','The target field must match this column’s confirmed term interpretation.',table=name,field=target)
  schema={'fields':[copy.deepcopy(official_fields[f]) for f in fields],'missingValues':['']};local={h:f for h,f in zip(table['headers'],fields)}
  keys=[local[k] for k in table.get('primaryKey',[]) if k in local]
  if keys:
   if keys!=key_fields(official.get('primaryKey')):add('DWC-PREP-PRIMARY','Declared identifier does not match the review provider primary key.',table=name)
   schema['primaryKey']=keys
  elif any(f.get('constraints',{}).get('required') and f['name'] not in fields for f in official['fields']):add('DWC-PREP-REQUIRED','Review table requires an identifier field that was not mapped.',table=name)
  path=name+'.csv';files[path]=csv_bytes(fields,table['rows']);resource={'name':name,'path':path,'profile':'tabular-data-resource','format':'csv','mediatype':'text/csv','encoding':'utf-8','dialect':{'lineTerminator':'\n'},'schema':schema,'bytes':len(files[path]),'hash':'sha256:'+hashlib.sha256(files[path]).hexdigest()};resources.append(resource);selected[name]={'table':table,'resource':resource,'local':local,'official':official}
 byid={v['table']['id']:v for v in selected.values()}
 for relation in project['relationships']:
  child=byid.get(relation['fromTable']);parent=byid.get(relation['toTable'])
  if not child or not parent:add('DWC-PREP-RELATIONSHIP','A declared relationship cannot be omitted from preparation.');continue
  source_fields=relation.get('fromFields') or [relation.get('fromField')];target_fields=relation.get('toFields') or [relation.get('toField')]
  mapped_source=[child['local'].get(field) for field in source_fields];mapped_target=[parent['local'].get(field) for field in target_fields]
  if len(mapped_source)!=len(mapped_target) or any(field is None for field in mapped_source+mapped_target):
   add('DWC-PREP-RELATIONSHIP','Every component of a declared relationship must be mapped.');continue
  fk={'fields':mapped_source[0] if len(mapped_source)==1 else mapped_source,'reference':{'resource':parent['resource']['name'] if child is not parent else '', 'fields':mapped_target[0] if len(mapped_target)==1 else mapped_target}}
  if not any(candidate['fields']==fk['fields'] and candidate['reference']==fk['reference'] for candidate in child['official'].get('foreignKeys',[])):add('DWC-PREP-RELATIONSHIP','Declared relationship differs from the review provider; review the identity and foreign-key mappings.',table=child['resource']['name'])
  child['resource']['schema'].setdefault('foreignKeys',[]).append(fk)
 descriptor={'profile':PROFILE,'id':project['id'],'title':project['metadata']['title']['value'],'created':project['createdAt'],'version':'1.0','resources':resources,'biorescue:preparationStatus':'Unratified review-schema preparation; no formal conformance assertion','biorescue:schemaProvider':review.summary()}
 files['datapackage.json']=json.dumps(descriptor,ensure_ascii=False,indent=2).encode('utf-8')
 stream=io.BytesIO()
 with zipfile.ZipFile(stream,'w') as archive:
  for path,data in files.items():archive.writestr(path,data)
 with zipfile.ZipFile(io.BytesIO(stream.getvalue())) as archive:checks=preflight(archive,descriptor,review.metadata['providerId'])
 checks['findings']=findings+checks['findings'];checks['guidePreflightPassed']=checks['guidePreflightPassed'] and not any(f['severity']=='Error' for f in findings)
 for finding in findings:checks['findingCountsBySeverity'][finding['severity']]=checks['findingCountsBySeverity'].get(finding['severity'],0)+1
 checks['preparationReady']=checks['guidePreflightPassed'];checks['status']='Review-schema preparation ready for inspection' if checks['preparationReady'] else 'Preparation needs mapping or data repairs'
 provenance={'projectId':project['id'],'projectRevision':project.get('revision',0),'applicationVersion':APP_VERSION,'preparedAt':datetime.now(timezone.utc).isoformat(),'schemaProvider':review.summary(),'mappings':mapping,'sources':[{'id':r['id'],'name':r['name'],'sha256':r['sha256']} for r in project['resources']],'audit':project['audit'],'metadata':project['metadata'],'fieldInterpretations':{t['id']:t['columns'] for t in project['tables']},'originalsIncluded':False,'scientificValuesTranslated':False}
 files['preparation-provenance.json']=json.dumps(provenance,ensure_ascii=False,indent=2).encode('utf-8');files['guide-validation.json']=json.dumps(checks,ensure_ascii=False,indent=2).encode('utf-8');files['README.txt']=b'PRIVATE REVIEW-SCHEMA PREPARATION\nThis ZIP is a transfer wrapper. Extract to inspect datapackage.json and literal CSV files. The ratified guide and a separately pinned TDWG-linked review schema provider are used. Ratified versioned machine-schema conformance is NOT claimed. Inspect guide-validation.json and preparation-provenance.json. Original bytes remain in the Workbench preservation package; keep that independent package too. This draft may contain precise locations and private metadata.\n';files['checksums.sha256']=''.join(hashlib.sha256(data).hexdigest()+'  '+path+'\n' for path,data in files.items()).encode()
 return descriptor,checks,files

def export(payload):
 _,checks,files=prepare(payload)
 if not checks['preparationReady']:raise ValueError('Preparation has unresolved findings. Review the preview; no package was exported.')
 stream=io.BytesIO()
 with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as archive:
  for path,data in files.items():archive.writestr(path,data)
 return stream.getvalue()
