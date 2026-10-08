"""Local, pinned scientific-format validators; findings never modify source values."""
import csv,io,json,hashlib,re,math
from datetime import datetime
from pathlib import Path
from upgrades import safe_archive
ROOT=Path(__file__).resolve().parent/'vendor/biodiversity'
def verify_schemas():
    for record in json.loads((ROOT/'sources.json').read_text()):
        if hashlib.sha256((ROOT/record['path']).read_bytes()).hexdigest()!=record['sha256']:raise ValueError('Biodiversity schema integrity mismatch: '+record['path'])
def finding(code,detail,layer='structure',severity='Error',**where):return dict(code=code,description=detail,layer=layer,severity=severity,**where)
def camtrap_descriptor(descriptor):
    verify_schemas()
    try:
        from jsonschema import Draft4Validator,FormatChecker
        from referencing import Registry,Resource
        from referencing.jsonschema import DRAFT4
    except ImportError:return {'status':'Unavailable','findings':[],'reason':'Install requirements-standards.txt.'}
    dictionary=json.loads((ROOT.parent/'schemas/dictionary.json').read_text());base={'$schema':'http://json-schema.org/draft-04/schema#','definitions':dictionary['definitions'],'$ref':'#/definitions/dataPackage'}
    geo=json.loads((ROOT/'dependencies/schema-store-geojson.json').read_text());profile=json.loads((ROOT/'camtrap-1.0.2/camtrap-dp-profile.json').read_text())
    def deny(uri):raise ValueError('Unvendored external schema reference refused: '+uri)
    registry=Registry(retrieve=deny).with_resources([(url,Resource.from_contents(data,default_specification=DRAFT4)) for url,data in [('https://specs.frictionlessdata.io/schemas/data-package.json',base),('http://json.schemastore.org/geojson.json',geo),('https://json.schemastore.org/geojson.json',geo),('https://geojson.org/schema/GeoJSON.json',json.loads((ROOT/'dependencies/geojson-rfc.json').read_text()))]])
    errors=[];roles=profile['allOf'][1]['properties']['contributors']['items']['properties']['role']['enum']
    for e in Draft4Validator(profile,registry=registry,format_checker=FormatChecker()).iter_errors(descriptor):
        path=list(e.absolute_path);conflict=e.validator=='enum' and len(path)==3 and path[0]=='contributors' and path[2]=='role' and e.instance in roles
        errors.append(finding('CAMTRAP-BASE-COMPATIBILITY' if conflict else 'CAMTRAP-DESCRIPTOR',('The official Camtrap profile permits this role but the pinned Frictionless v1 base schema rejects it: '+e.message) if conflict else e.message,'dependency' if conflict else 'structure','Warning' if conflict else 'Error',path='/'.join(map(str,path))))
    status='Descriptor has errors' if any(e['severity']=='Error' for e in errors) else 'Descriptor has unresolved base-schema compatibility warnings' if errors else 'Descriptor schema validated'
    return {'status':status,'findings':errors,'schemaVersion':'1.0.2','scientificallyValidated':False,'baseSchema':'Pinned Frictionless v1 commit 16ef8f781ccc0a099ae7a268591f45fe77e87e78; compatibility warnings prevent an unqualified conformance claim.'}

def cast(value,field):
    kind=field.get('type','string');fmt=field.get('format')
    if kind in ['string','any']:return value
    if kind=='integer':
        if not re.fullmatch('[+-]?[0-9]+',value):raise ValueError('Expected a literal integer.')
        return int(value)
    if kind=='number':
        if not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?',value):raise ValueError('Expected a finite decimal number.')
        number=float(value)
        if not math.isfinite(number):raise ValueError('Expected a finite decimal number.')
        return number
    if kind=='boolean':
        if value in field.get('trueValues',['true','True','TRUE','1']):return True
        if value in field.get('falseValues',['false','False','FALSE','0']):return False
        raise ValueError('Expected a declared boolean value.')
    if kind=='datetime':return datetime.strptime(value,fmt) if fmt and fmt!='default' else datetime.fromisoformat(value.replace('Z','+00:00'))
    raise ValueError('Unsupported field type: '+kind)
def camtrap_tables(tables):
    verify_schemas();findings=[];byname={};checked=0
    for table in tables:
        name=table['name'].lower()
        if name in byname:findings.append(finding('CAMTRAP-AMBIGUOUS','Multiple tables have this name; select the intended resource explicitly.','ambiguity',table=name))
        byname[name]=table
    schemas={name:json.loads((ROOT/'camtrap-1.0.2'/(name+'-table-schema.json')).read_text()) for name in ['deployments','media','observations']}
    for name,schema in schemas.items():
        t=byname.get(name)
        if not t:findings.append(finding('CAMTRAP-TABLE','Required table is absent.',table=name));continue
        headers=t['headers'];unique={};fieldmap={f['name']:f for f in schema['fields']}
        for field in schema['fields']:
            if field['name'] not in headers:findings.append(finding('CAMTRAP-COLUMN','Standard field is absent: '+field['name'],table=name,field=field['name']))
        for n,row in enumerate(t['rows'],2):
            checked+=1
            if len(row)!=len(headers):findings.append(finding('CAMTRAP-WIDTH','Record width differs from header.',table=name,row=n));continue
            for c,h in enumerate(headers):
                if h not in fieldmap:continue
                field=fieldmap[h];constraints=field.get('constraints',{});value=row[c];where={'table':name,'row':n,'field':h}
                if value in schema.get('missingValues',['']):
                    if constraints.get('required'):findings.append(finding('CAMTRAP-REQUIRED','Required value is missing.',**where))
                    continue
                try:parsed=cast(value,field)
                except (ValueError,OverflowError) as exc:findings.append(finding('CAMTRAP-TYPE',str(exc),**where));continue
                if 'enum' in constraints and parsed not in constraints['enum']:findings.append(finding('CAMTRAP-VOCABULARY','Value is outside the declared vocabulary.','vocabulary',**where))
                if 'pattern' in constraints and not re.search(constraints['pattern'],value):findings.append(finding('CAMTRAP-PATTERN','Value does not match the required pattern.',**where))
                for key,invalid in [('minimum','minimum' in constraints and parsed<constraints.get('minimum',0) if isinstance(parsed,(int,float)) else False),('maximum','maximum' in constraints and parsed>constraints.get('maximum',0) if isinstance(parsed,(int,float)) else False),('minLength',len(value)<constraints.get('minLength',0)),('maxLength',len(value)>constraints.get('maxLength',10**20))]:
                    if invalid:findings.append(finding('CAMTRAP-'+key.upper(),'Value violates '+key+'.',**where))
                if constraints.get('unique'):
                    seen=unique.setdefault(h,set())
                    if value in seen:findings.append(finding('CAMTRAP-UNIQUE','Duplicate literal identifier/value.',**where))
                    seen.add(value)
            for start,end in [('deploymentStart','deploymentEnd'),('eventStart','eventEnd')]:
                if start in headers and end in headers:
                    try:
                        if cast(row[headers.index(start)],fieldmap[start])>cast(row[headers.index(end)],fieldmap[end]):findings.append(finding('CAMTRAP-TEMPORAL','Start is after end; review source conventions.','scientific','Warning',table=name,row=n))
                    except (ValueError,TypeError):pass
        for fk in schema.get('foreignKeys',[]):
            parent=byname.get(fk['reference']['resource']);field=fk['fields'];target=fk['reference']['fields']
            if not parent or field not in headers or target not in parent['headers']:continue
            keys={row[parent['headers'].index(target)] for row in parent['rows'] if len(row)==len(parent['headers'])};index=headers.index(field)
            for n,row in enumerate(t['rows'],2):
                if len(row)==len(headers) and row[index] and row[index] not in keys:findings.append(finding('CAMTRAP-FOREIGN-KEY','Reference has no parent record.','relationships',table=name,row=n,field=field))
    return {'standard':'Camtrap DP','version':'1.0.2','status':'Table checks have errors' if any(f['severity']=='Error' for f in findings) else 'Implemented table checks passed','findings':findings,'recordsChecked':checked,'scientificallyValidated':False,'coverage':'Official field presence, required values, literal types/formats, vocabulary, pattern, ranges/length, uniqueness, foreign keys; temporal ordering is a separate advisory check. Not a claim of all publication/media-content/profile semantics.'}
def eml_validate(data):
    verify_schemas()
    try:from lxml import etree
    except ImportError:return {'standard':'EML','version':'2.2.0','status':'Unavailable','findings':[],'reason':'Install requirements-standards.txt for lxml.'}
    if len(data)>20*1024*1024:raise ValueError('EML limit: 20 MiB.')
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('DTD/entity declarations are not accepted.')
    parser=etree.XMLParser(no_network=True,resolve_entities=False,load_dtd=False)
    try:doc=etree.fromstring(data,parser)
    except etree.XMLSyntaxError as exc:return {'standard':'EML','version':'2.2.0','status':'Malformed XML','findings':[finding('EML-XML',str(exc))]}
    if doc.getroottree().docinfo.doctype:raise ValueError('DTD declarations are not accepted.')
    schema=etree.XMLSchema(etree.parse(str(ROOT/'eml-2.2.0/eml.xsd'),parser));valid=schema.validate(doc)
    errors=[finding('EML-XSD',e.message,line=e.line) for e in schema.error_log]
    return {'standard':'EML','version':'2.2.0','status':'XSD validated' if valid else 'XSD validation errors','findings':errors,'xsdValidated':valid,'scientificallyValidated':False,'coverage':'Complete vendored 2.2.0 XSD grammar; references/ID semantic consistency and scientific completeness are not established by XSD alone.'}
def validate_uploaded(data,name,provider_id=None):
    if name.lower().endswith('.xml'):return eml_validate(data)
    with safe_archive(data) as z:
        if 'ro-crate-metadata.json' in z.namelist():
            from ro_crate import check
            return check(json.loads(z.read('ro-crate-metadata.json')), {entry.filename:z.read(entry) for entry in z.infolist() if not entry.is_dir()})
        if 'datapackage.json' not in z.namelist():raise ValueError('Package must contain datapackage.json at its root.')
        descriptor=json.loads(z.read('datapackage.json'))
        if not isinstance(descriptor,dict):raise ValueError('Package descriptor must be a JSON object.')
        profile=descriptor.get('profile','')
        from dwc_dp import PROFILE,preflight
        if profile==PROFILE:return preflight(z,descriptor,provider_id)
        if not isinstance(profile,str):raise ValueError('Package profile must be a string.')
        if not isinstance(descriptor.get('resources'),list):raise ValueError('Package resources must be an array.')
        if 'camtrap' not in profile:raise ValueError('This validator accepts Camtrap DP 1.0.2 packages or EML XML. Other profiles remain explicitly unsupported.')
        metadata=camtrap_descriptor(descriptor);tables=[]
        for resource in descriptor.get('resources',[]):
            if not isinstance(resource,dict):raise ValueError('Invalid resource descriptor.')
            if resource.get('name') not in ['deployments','media','observations']:continue
            path=resource.get('path')
            if not isinstance(path,str) or path not in z.namelist() or path.startswith('/') or '..' in path.split('/') or ':' in path:raise ValueError('Resource must refer to a preserved local ZIP member; external URLs are not fetched.')
            with io.TextIOWrapper(z.open(path),encoding='utf-8-sig',newline='') as stream:
                reader=csv.reader(stream,strict=True);headers=next(reader,None);rows=[]
                if not headers:raise ValueError('Standard table is empty; a header is required.')
                if len(headers)>250:raise ValueError('Standard table limit: 250 columns.')
                for row in reader:
                    if len(rows)>=100000:raise ValueError('Standard table limit: 100,000 rows.')
                    rows.append(row)
            tables.append({'name':resource['name'],'headers':headers,'rows':rows})
        report=camtrap_tables(tables);report['descriptor']=metadata;report['findings']=metadata['findings']+report['findings'];report['status']='Descriptor validation Unavailable; table checks only' if metadata['status']=='Unavailable' else 'Validation findings require review' if report['findings'] else 'Implemented descriptor and table checks passed';return report
