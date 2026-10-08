"""Guide checks and explicitly selected TDWG-linked review schemas; never runtime fetch."""
import csv,gzip,io,re,hashlib
from pathlib import PurePosixPath
from schema_providers import provider
PROFILE='http://rs.tdwg.org/dwc-dp/1.0/dwc-dp-profile.json'
GUIDE='https://dwc.tdwg.org/dp/'
def capability():
 return {'standard':'Darwin Core Data Package','targetVersion':'1.0','guideVersion':'2026-05-26','profile':PROFILE,'status':'Guide checks available; ratified schema conformance pending upstream','guideRatified':True,'officialSchemasVendored':False,'reviewSchemasVendored':True,'conformanceAvailable':False,'runtimeNetwork':False,'providers':[{'providerId':'tdwg-review-2026-07','releaseStatus':'review-draft','schemaVersion':'1.0-DEV','ratified':False,'reviewSource':'https://github.com/tdwg/dwc/issues/903'}],'reason':'The guide is ratified. TDWG’s July 2026 review links the initial schemas hosted by GBIF; this build pins that review set separately. Versioned ratified schemas remain pending upstream publication and ratification.','import':'Generic package preservation and guide checks are available. Review-schema checks require explicit selection.','export':'Guide-based preparation is independent of formal conformance; no ratified schema claim is made.'}
def key_fields(value):return [value] if isinstance(value,str) else value if isinstance(value,list) and all(isinstance(x,str) for x in value) else []
def preflight(archive,descriptor,provider_id=None):
 selected=provider(provider_id);findings=[];finding_counts={};counts={};tables={};names=set()
 def record(finding):
  severity=finding.get("severity","Error");finding_counts[severity]=finding_counts.get(severity,0)+1
  if len(findings)<500:findings.append(finding)
 def add(code,description,severity='Error',**where):
  record(dict(code=code,severity=severity,layer='standard',description=description,source=GUIDE,ruleVersion='2026-05-26',**where))
 if not isinstance(descriptor,dict):descriptor={};add('DWC-DP-DESCRIPTOR','The descriptor must be an object.')
 resources=descriptor.get('resources',[])
 if descriptor.get('profile')!=PROFILE:add('DWC-DP-PROFILE','The descriptor must identify the target versioned normative profile; review checks do not replace that target.')
 if 'datapackage.json' not in archive.namelist():add('DWC-DP-ROOT','datapackage.json must be at the package root.')
 if not isinstance(resources,list) or not resources:add('DWC-DP-RESOURCES','A package needs at least one resource.');resources=[]
 for resource in resources:
  if not isinstance(resource,dict):add('DWC-DP-RESOURCE','Resource descriptors must be objects.');continue
  name=resource.get('name');where={'table':name if isinstance(name,str) else ''}
  if not isinstance(name,str) or not name or name in names:add('DWC-DP-NAME','Resource names must be present and distinct.',**where);continue
  names.add(name);path=resource.get('path')
  if not isinstance(path,str) or not path or PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts or '\\' in path or ':' in path:add('DWC-DP-PATH','Resources must use local package paths.',**where);continue
  if path not in archive.namelist():add('DWC-DP-MISSING-FILE','Declared resource is absent.',**where);continue
  if archive.getinfo(path).file_size>20*1024*1024:add('DWC-DP-RESOURCE-LIMIT','Resource exceeds the 20 MiB guide-check limit.',**where);continue
  payload=archive.read(path)
  if 'bytes' in resource and (isinstance(resource['bytes'],bool) or not isinstance(resource['bytes'],int) or resource['bytes']!=len(payload)):add('DWC-DP-BYTES','Declared byte length differs from the retained resource bytes.',**where)
  digest=resource.get('hash')
  if digest is not None:
   if isinstance(digest,str) and re.fullmatch(r'sha256:[a-fA-F0-9]{64}',digest):
    if hashlib.sha256(payload).hexdigest()!=digest.split(':',1)[1].lower():add('DWC-DP-HASH','Declared SHA-256 differs from the retained resource bytes.',**where)
   else:add('DWC-DP-HASH-UNSUPPORTED','The declared checksum format is not verified by this local SHA-256 adapter.','Warning',**where)
  if resource.get('profile')!='tabular-data-resource':
   if selected and name in selected.reserved():add('DWC-DP-RESERVED-NAME','A non-table resource uses a reserved review-schema table name.',**where)
   continue
  if resource.get('mediatype')!='text/csv':add('DWC-DP-CSV','Table resources must declare text/csv; csv and tsv formats are both permitted.',**where)
  schema=resource.get('schema')
  if not isinstance(schema,dict):add('DWC-DP-INLINE-SCHEMA','A table schema must be an inline object.',**where);continue
  fields=schema.get('fields');fields=fields if isinstance(fields,list) else []
  if not fields:add('DWC-DP-FIELDS','Fields must be a nonempty list.',**where)
  valid=[]
  for field in fields:
   if not isinstance(field,dict):add('DWC-DP-FIELD','A field descriptor must be an object.',**where);continue
   valid.append(field)
   for key in ['name','title','description','type']:
    if not isinstance(field.get(key),str) or not field[key].strip():add('DWC-DP-FIELD-'+key.upper(),'Field requires '+key+'.',field=field.get('name'),**where)
   if not isinstance(field.get('dcterms:isVersionOf'),str) or not re.match(r'^https?://[^\s]+$',field['dcterms:isVersionOf']):add('DWC-DP-TERM-IRI','Each field needs an absolute term URL.',field=field.get('name'),**where)
  headers=[f.get('name') for f in valid]
  if len(set(headers))!=len(headers):add('DWC-DP-FIELD-NAMES','Field names must be distinct.',**where)
  dialect=resource.get('dialect',{})
  if not isinstance(dialect,dict):add('DWC-DP-DIALECT','Dialect must be an object.',**where);continue
  delimiter=dialect.get('delimiter',',');quote=dialect.get('quoteChar','"');has_header=dialect.get('header',True)
  if not isinstance(delimiter,str) or len(delimiter)!=1 or not isinstance(quote,str) or len(quote)!=1 or not isinstance(has_header,bool):add('DWC-DP-DIALECT','Delimiter, quote character and header flag are invalid.',**where);continue
  try:
   raw=archive.read(path)
   if path.endswith('.gz'):
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:raw=stream.read(20*1024*1024+1)
   if len(raw)>20*1024*1024:raise ValueError('Resource exceeds the 20 MiB guide-check limit.')
   text=raw.decode(resource.get('encoding','utf-8'),errors='strict');reader=csv.reader(io.StringIO(text,newline=''),delimiter=delimiter,quotechar=quote,doublequote=dialect.get('doubleQuote',True),strict=True)
   if has_header and next(reader,None)!=headers:add('DWC-DP-HEADER','CSV header order differs from declared fields.',**where)
   rows=[]
   for number,row in enumerate(reader,2 if has_header else 1):
    if len(row)!=len(fields):add('DWC-DP-WIDTH','Record width differs from declared fields.',row=number,**where);continue
    rows.append((number,row))
   counts[name]=len(rows);tables[name]={'headers':headers,'rows':rows,'schema':schema}
   missing=schema.get('missingValues',['']);missing=missing if isinstance(missing,list) else ['']
   unique={}
   from biodiversity_validation import cast
   for number,row in rows:
    for index,field in enumerate(valid):
     value=row[index];constraints=field.get('constraints',{});constraints=constraints if isinstance(constraints,dict) else {};location=dict(table=name,row=number,field=field.get('name'))
     if value in missing:
      if constraints.get('required'):add('DWC-DP-REQUIRED-VALUE','Required field has a declared missing value.',**location)
      continue
     try:
      typed=cast(value,field)
      if 'enum' in constraints and typed not in constraints['enum']:raise ValueError('Value is outside the declared vocabulary.')
      if 'minimum' in constraints and typed<constraints['minimum']:raise ValueError('Value is below the declared minimum.')
      if 'maximum' in constraints and typed>constraints['maximum']:raise ValueError('Value is above the declared maximum.')
      if 'minLength' in constraints and len(value)<constraints['minLength']:raise ValueError('Value is shorter than declared.')
      if 'maxLength' in constraints and len(value)>constraints['maxLength']:raise ValueError('Value is longer than declared.')
      if constraints.get('unique'):
       seen=unique.setdefault(index,set())
       if value in seen:raise ValueError('Duplicate literal value in a unique field.')
       seen.add(value)
     except (ValueError,TypeError) as exc:
      unsupported=str(exc).startswith('Unsupported field type:')
      add('DWC-DP-VALUE-UNSUPPORTED' if unsupported else 'DWC-DP-VALUE',str(exc),'Warning' if unsupported else 'Error',**location)
  except (UnicodeError,LookupError,ValueError,OSError,csv.Error,TypeError) as exc:add('DWC-DP-READ','Resource cannot be read under its declared encoding/dialect: '+str(exc),**where)
  if selected:
   official=selected.table(name)
   if not official:add('DWC-DP-REVIEW-TABLE','Table name is absent from the pinned review provider.',**where)
   else:
    fieldmap={f['name']:f for f in official['fields']}
    keys=key_fields(schema.get('primaryKey'));allowed=key_fields(official.get('primaryKey'))
    if keys and any(k not in allowed for k in keys):add('DWC-DP-REVIEW-PRIMARY','Primary key is not declared by the review table schema.',**where)
    for expected in official['fields']:
     if expected.get('constraints',{}).get('required') and expected['name'] not in headers:add('DWC-DP-REVIEW-REQUIRED','A required review field is absent.',field=expected['name'],**where)
    relationships=schema.get('foreignKeys',[])
    for relation in relationships if isinstance(relationships,list) else []:
     if not isinstance(relation,dict):continue
     if not any(key_fields(relation.get('fields'))==key_fields(fk.get('fields')) and relation.get('reference')==fk.get('reference') for fk in official.get('foreignKeys',[])):add('DWC-DP-REVIEW-FOREIGN','Relationship is not declared by the review table schema.',**where)
    for f in valid:
     expected=fieldmap.get(f.get('name'))
     if not expected:add('DWC-DP-REVIEW-FIELD','Field is absent from this table in the review provider.',field=f.get('name'),**where)
     elif any(f.get(k)!=expected.get(k) for k in ['name','title','description','type','format','dcterms:isVersionOf','constraints']):add('DWC-DP-REVIEW-DESCRIPTOR','Field descriptor differs from the pinned review descriptor.',field=f.get('name'),**where)
 if not tables:add('DWC-DP-TABLE','At least one readable table resource is required.')
 indexes={}
 for name,t in tables.items():
  keys=key_fields(t['schema'].get('primaryKey'));positions=[t['headers'].index(k) for k in keys if k in t['headers']];missing=t['schema'].get('missingValues',['']);missing=missing if isinstance(missing,list) else ['']
  if keys and len(positions)!=len(keys):add('DWC-DP-PRIMARY-KEY','Primary key fields are absent.',table=name);continue
  seen=set()
  if keys:
   for number,row in t['rows']:
    value=tuple(row[i] for i in positions)
    if any(x in missing for x in value):add('DWC-DP-PRIMARY-NULL','Primary keys cannot be missing.',table=name,row=number)
    elif value in seen:add('DWC-DP-PRIMARY-DUPLICATE','Duplicate literal primary key.',table=name,row=number)
    seen.add(value)
  indexes[name]=(keys,seen)
 for name,t in tables.items():
  relationships=t['schema'].get('foreignKeys',[])
  if not isinstance(relationships,list):add('DWC-DP-FOREIGN-KEY','foreignKeys must be a list.',table=name);continue
  for fk in relationships:
   if not isinstance(fk,dict) or not isinstance(fk.get('reference'),dict):add('DWC-DP-FOREIGN-KEY','Foreign key descriptor is invalid.',table=name);continue
   local=key_fields(fk.get('fields'));ref=fk['reference'];target=ref.get('resource') or name;remote=key_fields(ref.get('fields'));parent=tables.get(target)
   if not local or len(local)!=len(remote) or any(k not in t['headers'] for k in local) or not parent or indexes.get(target,([],set()))[0]!=remote:add('DWC-DP-FOREIGN-TARGET','Foreign keys must reference the declared primary key of an included table.',table=name);continue
   positions=[t['headers'].index(k) for k in local];missing=t['schema'].get('missingValues',['']);missing=missing if isinstance(missing,list) else ['']
   for number,row in t['rows']:
    value=tuple(row[i] for i in positions)
    if not any(x in missing for x in value) and value not in indexes[target][1]:add('DWC-DP-FOREIGN-ORPHAN','Literal reference has no parent record.',table=name,row=number)
 if 'eml.xml' in archive.namelist():
  from biodiversity_validation import eml_validate
  for finding in eml_validate(archive.read('eml.xml')).get('findings',[]):record(finding)
 record(dict(code='DWC-DP-RATIFIED-SCHEMAS-PENDING',severity='Warning',layer='dependency',description=capability()['reason'],source=PROFILE,ruleVersion='1.0'))
 omitted=sum(finding_counts.values())-len(findings)
 if omitted:findings.append({'code':'DWC-DP-FINDINGS-TRUNCATED','severity':'Warning','layer':'diagnostic','description':'Additional findings are omitted from this display. Severity counts include every detected finding.','omittedFindings':omitted,'source':GUIDE,'ruleVersion':'2026-05-26'})
 passed=not finding_counts.get('Error',0)
 return {'standard':'Darwin Core Data Package','version':'1.0','guideVersion':'2026-05-26','status':'Implemented guide checks passed' if passed else 'Guide checks have errors','formalConformanceStatus':'Blocked externally: ratified versioned schemas pending','findings':findings,'findingCountsBySeverity':finding_counts,'omittedFindings':omitted,'findingsComplete':not omitted,'recordsRead':counts,'guidePreflightPassed':passed,'officialSchemasValidated':False,'provider':selected.summary() if selected else None,'reviewSchemasChecked':bool(selected),'scientificallyValidated':False,'transport':'ZIP transfer wrapper; extracted package root is checked. ZIP is not claimed as normative whole-package compression.','coverage':'Retained-resource byte lengths and declared SHA-256; implemented required values, literal types, vocabulary, ranges, lengths, uniqueness; guide descriptor, resource, inline fields, explicit dialect/encoding, width, literal primary-key and declared foreign-key checks. Undeclared real-world relationships, complete value constraints, and ratified descriptor correspondence are not established.'}
