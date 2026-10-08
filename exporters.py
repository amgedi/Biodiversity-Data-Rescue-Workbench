from biodiversity_validation import eml_validate
"""Open-format multi-resource packages. Public exports never include originals or audit snapshots."""
import io
import json
import re
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from xml.etree import ElementTree as ET
from rescue import csv_bytes, source_bytes, sha
from storage import validate
from standards import PROFILES, awareness

from upgrades import APP_VERSION as VERSION
STATUS=['Confirmed','Inferred','Unknown','Conflicting','Not Applicable']
def encoded(value):return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
def safe(value):return re.sub(r'[^a-zA-Z0-9_-]','-',value).strip('-').lower()[:70] or 'resource'
def value(p,key,confirmed=False):
    v=p['metadata'].get(key,{})
    return v.get('value','') if not confirmed or v.get('status')=='Confirmed' else ''


def structure_checks(p):
    checks=[]
    def add(layer,severity,title,detail):checks.append({'layer':layer,'severity':severity,'title':title,'detail':detail})
    for t in p['tables']:
        for c,h in zip(t['columns'],t['headers']):
            kind=c.get('dataType','string')
            if kind not in ['string','integer','number','boolean','date']:add('schema','Error',f'Unsupported type: {h}',kind)
            for r in t['rows']:
                v=r[t['headers'].index(h)]
                if not v:continue
                valid=True
                if kind=='integer':valid=bool(re.fullmatch(r'[+-]?\d+',v))
                elif kind=='number':
                    import math
                    try:valid=math.isfinite(float(v))
                    except ValueError:valid=False
                elif kind=='boolean':valid=v.lower() in ('true','false')
                elif kind=='date':
                    from datetime import date
                    try:date.fromisoformat(v);valid=bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}',v))
                    except ValueError:valid=False
                if not valid:add('schema','Error',f'Type mismatch: {t["name"]}.{h}',f'{kind} declaration does not fit all nonblank values.');break
            expected=c.get('allowedValues',[])
            if expected and any(r[t['headers'].index(h)] and r[t['headers'].index(h)] not in expected for r in t['rows']):add('schema','Error',f'Unexpected category: {h}','Working values violate declared allowed values.')
        keys=t.get('primaryKey',[])
        if keys:
            if any(h not in t['headers'] for h in keys):add('relationships','Error','Missing primary-key field',t['name']);continue
            indexes=[t['headers'].index(h) for h in keys];values=[tuple(r[c] for c in indexes) for r in t['rows']]
            if any(any(v=='' for v in row) for row in values):add('relationships','Error','Blank primary key',t['name'])
            if len(set(values))!=len(values):add('relationships','Error','Duplicate primary key',t['name'])
    for rel in p['relationships']:
        a=next((t for t in p['tables'] if t['id']==rel['fromTable']),None);b=next((t for t in p['tables'] if t['id']==rel['toTable']),None)
        if not a or not b or rel['fromField'] not in a['headers'] or rel['toField'] not in b['headers']:add('relationships','Error','Broken relationship','Referenced table or column is absent.');continue
        c=a['headers'].index(rel['fromField']);d=b['headers'].index(rel['toField']);parent=[r[d] for r in b['rows']]
        if b.get('primaryKey')!=[rel['toField']]:add('relationships','Error','Foreign-key target needs a primary key',f'{b["name"]}.{rel["toField"]} must be declared as the single-column primary key.')
        if len(set(parent))!=len(parent):add('relationships','Error','Nonunique relationship target',b['name'])
        parent_set=set(parent)
        missing=sum(1 for r in a['rows'] if r[c] and r[c] not in parent_set)
        if missing:add('relationships','Error','Missing referenced records',f'{missing} in {a["name"]}')
    return checks


def public_tables(p,policy):
    if policy.get('mode') not in ('redact','generalize'):raise ValueError('Choose redact or generalize for the public export.')
    precision=int(policy.get('precision',1))
    if not 0<=precision<=3:raise ValueError('Public precision must be 0–3 decimal places.')
    tables=deepcopy(p['tables'])
    for t in tables:
        for c,(h,col) in enumerate(zip(t['headers'],t['columns'])):
            candidate=bool(re.search(r'latitude|longitude|coordinate|easting|northing|geometry|footprint|geohash|(?:^|[^a-z])(?:lat|lon|lng)(?:$|[^a-z])',h+' '+col.get('originalName',''),re.I)) or col.get('term') in ('decimalLatitude','decimalLongitude','verbatimLatitude','verbatimLongitude') or col.get('sensitive',False)
            if not candidate:continue
            decimal=col.get('term') in ('decimalLatitude','decimalLongitude') and col.get('status')=='Confirmed'
            for row in t['rows']:
                if policy['mode']=='generalize' and decimal and not col.get('sensitive',False):
                    try:row[c]=str(round(float(row[c]),precision)) if row[c] else ''
                    except ValueError:row[c]=''
                else:row[c]=''
            col['description']='Public export: sensitive/coordinate values withheld or explicitly rounded.';col['dataType']='string';col['constraints']={};col['allowedValues']=[]
        # Export precision is not coordinate uncertainty, and hidden baselines must never travel in a public package.
        t.pop('originalTable',None);t.pop('legacyAudit',None)
    return tables


def eml_draft(p):
    missing=[k for k in ('title','creator','contact','description','license') if not value(p,k,True)]
    if missing:return None,{'status':'not generated','missingConfirmedFields':missing,'xsdValidated':False}
    organization=value(p,'organizations',True)
    if not organization or value(p,'creator',True)!=organization or value(p,'contact',True)!=organization:
        return None,{'status':'not generated','missingConfirmedFields':[],'xsdValidated':False,'warning':'This draft adapter supports a confirmed organization as creator/contact only. Record organizations and matching creator/contact explicitly; free-form party types are never guessed.'}
    ns='https://eml.ecoinformatics.org/eml-2.2.0';ET.register_namespace('eml',ns)
    root=ET.Element('{'+ns+'}eml',{'packageId':p['id'],'system':'Biodiversity Data Rescue Workbench'});dataset=ET.SubElement(root,'dataset')
    ET.SubElement(dataset,'title').text=value(p,'title',True)
    party=ET.SubElement(dataset,'creator');ET.SubElement(party,'organizationName').text=value(p,'creator',True)
    abstract=ET.SubElement(dataset,'abstract');ET.SubElement(abstract,'para').text=value(p,'description',True)
    rights=ET.SubElement(dataset,'intellectualRights');ET.SubElement(rights,'para').text=value(p,'license',True)
    party=ET.SubElement(dataset,'contact');ET.SubElement(party,'organizationName').text=value(p,'contact',True)
    if value(p,'methods',True):methods=ET.SubElement(dataset,'methods');step=ET.SubElement(methods,'methodStep');desc=ET.SubElement(step,'description');ET.SubElement(desc,'para').text=value(p,'methods',True)
    data=ET.tostring(root,encoding='utf-8',xml_declaration=True);checked=eml_validate(data)
    return data,{'status':'basic metadata; '+checked['status'],'missingConfirmedFields':[],'xsdValidated':checked.get('xsdValidated',False),'warning':'Confirmed matching organizational creator/contact only. Rich table/coverage metadata and semantic reference validation remain pending; no party type was inferred.'}


def report(p,checks):
    evidence_names=lambda refs: ', '.join(next((r['name'] for r in p['resources'] if r['id']==ref),ref) for ref in refs)
    lines=['# Biodiversity Rescue Report','',f'Project: {value(p,"title")}','',f'Application: {VERSION}',f'Project created: {p["createdAt"]}','', 'Technical validity is not scientific correctness.','', '## Original files','']
    for r in p['resources']:lines.extend([f'- {r["name"]} · {r["bytes"]} bytes · imported {r["importedAt"]}',f'  SHA-256: `{r["sha256"]}`',f'  Format: {r["format"]}; conversion: {r.get("conversionIssue") or "see structure observations"}'])
    lines+=['','## Tables','']
    for t in p['tables']:
        lines.append(f'- {t["name"]}: {len(t["rows"])} rows, {len(t["headers"])} columns; primary key: {t.get("primaryKey") or "not confirmed"}')
        for c in t['columns']:lines.append(f'  - {c["workingName"]}: {c["description"] or "meaning unknown"} [{c["status"]}]; term {c.get("term") or "unmapped"}; evidence {evidence_names(c.get("evidence",[])) or "none recorded"}; rationale {c.get("rationale","")}')
    for status in STATUS:
        lines+=['',f'## {status} metadata','']
        for key,m in p['metadata'].items():
            if m['status']==status:lines.append(f'- {key}: {m["value"] or "unknown"}; evidence: {evidence_names(m.get("evidence",[])) or "none recorded"}; rationale: {m.get("rationale","")}')
    lines+=['','## Relationships','']+[f'- {r["fromTable"]}.{r["fromField"]} → {r["toTable"]}.{r["toField"]}; {r["status"]}; {r["rationale"]}' for r in p['relationships']]
    lines+=['','## Repairs and provenance','']+[f'- {e["at"]} · {e["action"]}: {e["reason"]}' for e in p['audit']]
    lines+=['','## Validation','']+[f'- {c["severity"]} / {c["layer"]}: {c["title"]} — {c.get("detail","")}' for c in checks]
    lines+=['','## Standard capabilities','']+[f'- {profile["name"]} ({profile["version"]}): {profile["capability"]}' for profile in PROFILES.values()]
    lines+=['','## Remaining work','', 'Review unresolved unknowns and conflicts, validate all inferred meanings with evidence, confirm datum and date conventions, repair relationship errors, and obtain full official-schema validation before making standard-conformance claims.','', '## Exports','', 'Working CSVs, schemas, datapackage.json, metadata.json, original files, structure observations, audit, recipe, source manifest, validation, this report, checksums, and a portable project. EML draft and RO-Crate metadata included only if their metadata prerequisites are met.']
    return ('\n'.join(lines)+'\n').encode('utf-8')


def export_v2(payload):
    p=payload.get('project',payload);validate(p);policy=payload.get('policy',{'mode':'private'});public=policy.get('mode')!='private';checks=structure_checks(p)
    if payload.get('strict') and any(c['severity']=='Error' for c in checks):raise ValueError('Declared schema/relationship errors block strict export. Resolve them or choose preservation export, which includes unresolved diagnostics.')
    tables=public_tables(p,policy) if public else p['tables'];files={};names={t['id']:f't{i+1}-{safe(t["name"])}' for i,t in enumerate(tables)}
    descriptor={'profile':'data-package','name':safe(value(p,'title')),'id':p['id'],'title':value(p,'title'),'created':p['createdAt'],'version':'1.0','resources':[],'biorescue:applicationVersion':VERSION,'biorescue:standards':p['profiles'],'biorescue:validation':'Local subset checks only; no scientific correctness or full standard conformance asserted.'}
    for t in tables:
        name=names[t['id']];path=f'working/{name}.csv';files[path]=csv_bytes(t['headers'],t['rows']);fields=[]
        for h,col in zip(t['headers'],t['columns']):
            f={'name':h,'type':col.get('dataType','string'),'description':col['description'],'biorescue:unit':col.get('unit',''),'biorescue:interpretationStatus':col['status']}
            constraints=dict(col.get('constraints',{}))
            if col.get('allowedValues'):constraints['enum']=col['allowedValues']
            if constraints:f['constraints']=constraints
            if col.get('term') and col['status']=='Confirmed':f['dcterms:isVersionOf']=col['term'] if col['term'].startswith(('http://','https://')) else 'http://rs.tdwg.org/dwc/terms/'+col['term']
            fields.append(f)
        schema={'fields':fields,'missingValues':['']}
        if t.get('primaryKey') and not public:schema['primaryKey']=t['primaryKey']
        fk=[{'fields':r.get('fromFields') or r['fromField'],'reference':{'resource':names[r['toTable']],'fields':r.get('toFields') or r['toField']}} for r in p['relationships'] if r['fromTable']==t['id'] and r['toTable'] in names]
        if fk and not public:schema['foreignKeys']=fk
        files[f'schemas/{name}.schema.json']=encoded(schema)
        descriptor['resources'].append({'name':name,'path':path,'profile':'tabular-data-resource','format':'csv','mediatype':'text/csv','encoding':'utf-8','dialect':{'delimiter':',','lineTerminator':'\n','quoteChar':'"','doubleQuote':True},'schema':schema,'bytes':len(files[path]),'hash':'sha256:'+sha(files[path])})
    files['datapackage.json']=encoded(descriptor)
    if public:
        files['public-policy.json']=encoded({'mode':policy['mode'],'precision':policy.get('precision'),'warning':'Coordinate/marked-field suppression only. Free-text fields may still expose locations or identities. Review all exported values before release. Datum and true uncertainty are not inferred.'})
        files['README.txt']=b'PUBLIC COORDINATE EXPORT\nOriginals, project backups, evidence, audit snapshots, raw metadata and private reports deliberately excluded. Review remaining free-text fields for sensitive information. Import CSV columns as text to preserve identifiers and avoid formula execution.\n'
    else:
        for r in p['resources']:
            filename=re.sub(r'[^a-zA-Z0-9._-]','_',r['name'])[:120] or 'source'
            files[f'original/{r["id"]}-{filename}']=source_bytes(r, allow_empty=True)
        files['metadata.json']=encoded(p['metadata']);files['fields.json']=encoded({t['id']:t['columns'] for t in p['tables']});files['source-manifest.json']=encoded([{k:v for k,v in r.items() if k!='base64'} for r in p['resources']]);files['project.biorescue.json']=encoded(p);files['audit.json']=encoded(p['audit'])
        from report_v3 import report_data,report_html,report_markdown
        from validation_v3 import descriptor_validation,composite_checks
        machine=report_data(p,checks+composite_checks(p)+payload.get('issues',[]),payload.get('reportLanguage','en'));files['rescue-report.json']=encoded(machine);files['rescue-report.html']=report_html(machine);files['data-package-validation.json']=encoded(descriptor_validation(descriptor))
        active=set(p['undoStack']);files['recipe.json']=encoded({'recipeVersion':1,'projectSchemaVersion':p.get('projectSchemaVersion',3),'applicationVersion':VERSION,'projectId':p['id'],'sources':[{'id':r['id'],'name':r['name'],'sha256':r['sha256'],'bytes':r['bytes']} for r in p['resources']],'tableDefinitions':[{'id':t['id'],'resourceId':t['resourceId'],'parsing':t['parsing'],'sheet':t.get('sheet'),'expectedOriginalHeaders':t['originalTable']['headers']} for t in p['tables']],'steps':[{**e['operation'],'reason':e['reason']} for e in p['audit'] if e.get('operation') and e['id'] in active]})
        files['validation.json']=encoded({'localStructuralChecks':checks,'advisoryChecks':payload.get('issues',[]),'awareness':awareness(p),'scientificallyValidated':False});files['rescue-report.md']=report_markdown(machine)
        draft,status=eml_draft(p);files['eml-status.json']=encoded(status)
        if draft:
            files['eml-draft.xml']=draft;files['eml-xsd-validation.json']=encoded(eml_validate(draft))
        required=[k for k in ('title','description','license','creator','publicationDate') if not value(p,k,True)]
        creator=p['metadata'].get('creator',{})
        creator_type=creator.get('partyType')
        if creator_type not in {'Person','Organization'}:
            creator_type='Organization' if 'partyType' not in creator and value(p,'organizations',True) and value(p,'creator',True)==value(p,'organizations',True) else None
        if creator_type is None:required.append('confirmed explicit creator entity type')
        creator_id=creator.get('identifier') or '#custodian'
        contributor=p['metadata'].get('contributors',{})
        if creator.get('identifier') and contributor.get('identifier')==creator['identifier'] and contributor.get('status')=='Confirmed' and contributor.get('partyType') in {'Person','Organization'} and (contributor.get('value')!=creator.get('value') or contributor.get('partyType')!=creator_type):required.append('conflicting creator/contributor identifier')

        try:
            from datetime import date
            date.fromisoformat(value(p,'publicationDate',True))
        except ValueError:required.append('confirmed valid ISO publication date')
        files['README.txt']=b'BIODIVERSITY RESCUE PRESERVATION PACKAGE\nOriginal bytes and working copies are separate. No unknown scientific meaning was invented. Interpretations and evidence are user assertions. Review source-manifest, fields, validation and rescue-report before reuse. Read eml-status.json and eml-xsd-validation.json for actual local EML 2.2.0 XSD results; schema validity does not establish scientific completeness. Darwin Core mappings do not constitute DwC-DP compliance. CSV must be imported as text to prevent formula execution and preserve identifiers. This private package includes sensitive original and history content; use a public export for coordinate suppression.\n'
    if not public:
        files['package-manifest.json']=encoded({'packageVersion':1,'createdAt':datetime.now(timezone.utc).isoformat(),'applicationVersion':VERSION,'projectSchemaVersion':p.get('projectSchemaVersion',2),'standards':p['profiles'],'recipe':'recipe.json','validation':'validation.json','report':'rescue-report.html','resources':[{'path':path,'bytes':len(data),'sha256':sha(data),'role':'original' if path.startswith('original/') else 'working' if path.startswith('working/') else 'documentation'} for path,data in files.items()]})
        files['ARCHIVE_README.md']=b'# Biodiversity rescue preservation package\n\nOpen rescue-report.html or rescue-report.md first. Working CSVs and schemas describe literal retained values; metadata.json and fields.json document uncertainty. Original bytes are in original/; do not edit them. recipe.json and audit.json record transformations. project.biorescue.json is internal application state, not required to read the scientific data. checksums.sha256 lists each file: use a SHA-256 tool to compare its bytes. No checksum establishes authorship. Review validation.json and data-package-validation.json: structural validity is not scientific correctness. EML coverage and XSD results are recorded separately in eml-status.json and eml-xsd-validation.json. No DwC-DP/Camtrap/full RO-Crate conformance is asserted. This PRIVATE package may contain precise locations and contacts.\n'
        if not required:
            graph=[{'@id':'ro-crate-metadata.json','@type':'CreativeWork','conformsTo':{'@id':'https://w3id.org/ro/crate/1.3'},'about':{'@id':'./'}},{'@id':'./','@type':'Dataset','name':value(p,'title',True),'description':value(p,'description',True),'datePublished':value(p,'publicationDate',True),'license':value(p,'license',True),'creator':{'@id':creator_id},'hasPart':[{'@id':path} for path in files]},{'@id':creator_id,'@type':creator_type,'name':value(p,'creator',True)}]
            contributor=p['metadata'].get('contributors',{})
            if contributor.get('status')=='Confirmed' and contributor.get('value') and contributor.get('partyType') in {'Person','Organization'}:
                contributor_id=contributor.get('identifier') or '#contributor'
                if contributor_id==creator_id:
                    if contributor.get('value')==creator.get('value') and contributor['partyType']==creator_type:graph[1]['contributor']={'@id':creator_id}
                    else:
                        contributor_id='#contributor';graph[1]['contributor']={'@id':contributor_id};graph.append({'@id':contributor_id,'@type':contributor['partyType'],'name':contributor['value'],'identifier':contributor.get('identifier','')})
                else:
                    graph[1]['contributor']={'@id':contributor_id};graph.append({'@id':contributor_id,'@type':contributor['partyType'],'name':contributor['value']})
            software_id='#workbench-'+VERSION
            graph.append({'@id':software_id,'@type':'SoftwareApplication','name':'Biodiversity Data Rescue Workbench','softwareVersion':VERSION})
            entities={e['@id']:e for e in graph}
            for table in tables:
                original=next((path for path in files if path.startswith('original/'+table['resourceId']+'-')),None)
                working='working/'+names[table['id']]+'.csv'
                if original:entities.setdefault(working,{'@id':working,'@type':'File'})['isBasedOn']={'@id':original}
            graph.extend({'@id':path,'@type':'File','name':path,'contentSize':str(len(data)),'sha256':sha(data),**({'isBasedOn':entities[path]['isBasedOn']} if path in entities and 'isBasedOn' in entities[path] else {})} for path,data in files.items())
            originals=[{'@id':path} for path in files if path.startswith('original/')]
            graph[1]['isBasedOn']=originals
            graph[1]['subjectOf']=[{'@id':'audit.json'},{'@id':'recipe.json'}]
            graph.append({'@id':'#workbench-export','@type':'CreateAction','name':'Preservation export','description':'Generated working CSVs and preservation documentation from the retained sources and recorded project state. No human agent or scientific authorship is inferred.','instrument':{'@id':software_id},'object':originals+[{'@id':'project.biorescue.json'},{'@id':'recipe.json'},{'@id':'audit.json'}],'result':[{'@id':path} for path in files if not path.startswith('original/') and path not in {'project.biorescue.json','recipe.json','audit.json'}],'endTime':datetime.now(timezone.utc).isoformat()})
            crate={'@context':'https://w3id.org/ro/crate/1.3/context','@graph':graph}
            from ro_crate import check
            files['ro-crate-validation.json']=encoded(check(crate,files))
            files['ro-crate-metadata.json']=encoded(crate)
        else:files['ro-crate-status.json']=encoded({'generated':False,'missingConfirmedFields':required,'fullProfileValidated':False})
    files['checksums.sha256']=''.join(f'{sha(data)}  {path}\n' for path,data in files.items()).encode()
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for path,data in files.items():z.writestr(path,data)
    return output.getvalue()
