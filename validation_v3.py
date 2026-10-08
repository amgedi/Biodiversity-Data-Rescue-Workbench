"""Vendored official JSON Schema validation plus explicit local table checks."""
import csv, hashlib, io, json
from pathlib import Path
ROOT=Path(__file__).resolve().parent/'vendor/schemas'
def descriptor_validation(descriptor):
    try:from jsonschema import Draft4Validator,FormatChecker
    except ImportError:return {'status':'Unavailable','errors':[],'reason':'Install the pinned optional jsonschema dependency; generated is not validated.'}
    sources=json.loads((ROOT/'sources.json').read_text())
    for r in sources:
        if hashlib.sha256((ROOT/r['name']).read_bytes()).hexdigest()!=r['sha256']:raise ValueError('Vendored standard checksum mismatch.')
    dictionary=json.loads((ROOT/'dictionary.json').read_text())
    def check(value,definition,prefix):
        schema={'$schema':'http://json-schema.org/draft-04/schema#','definitions':dictionary['definitions'],'$ref':'#/definitions/'+definition}
        return [{'code':'DP1-JSONSCHEMA','severity':'Error','layer':'standard','path':prefix+'/'+ '/'.join(map(str,e.path)),'description':e.message,'source':'Frictionless Data Package v1 official schema','ruleVersion':sources[0]['commit']} for e in Draft4Validator(schema,format_checker=FormatChecker()).iter_errors(value)]
    errors=check(descriptor,'dataPackage','descriptor')
    resources=descriptor.get('resources',[])
    for i,r in enumerate(resources if isinstance(resources,list) else []):
        if not isinstance(r,dict):continue
        errors+=check(r,'tabularDataResource',f'resources/{i}')
        if isinstance(r.get('schema'),dict):errors+=check(r['schema'],'tableSchema',f'resources/{i}/schema')
        if isinstance(r.get('dialect'),dict):errors+=check(r['dialect'],'csvDialect',f'resources/{i}/dialect')
    return {'status':'Generated with validation errors' if errors else 'Generated and descriptor/schema validated','errors':errors,'sourceCommit':sources[0]['commit'],'scientificallyValidated':False,'scope':'Official v1 JSON Schemas for descriptor, tabular resources, Table Schema and CSV dialect. Cell/key checks are a separate local subset; full Table Schema value semantics are not certified.'}
def composite_checks(p):
    result=[];byid={t['id']:t for t in p['tables']}
    for r in p['relationships']:
        if not r.get('fromFields'):continue
        a,b=byid[r['fromTable']],byid[r['toTable']];left,right=r['fromFields'],r['toFields']
        if len(left)!=len(right) or not left or any(h not in a['headers'] for h in left) or any(h not in b['headers'] for h in right):raise ValueError('Invalid composite relationship fields.')
        ai=[a['headers'].index(h) for h in left];bi=[b['headers'].index(h) for h in right]
        keys={tuple(row[c] for c in bi) for row in b['rows']};orphans=[i for i,row in enumerate(a['rows']) if any(row[c] for c in ai) and tuple(row[c] for c in ai) not in keys]
        if orphans:result.append({'code':'REL-COMPOSITE-ORPHAN','layer':'relationships','severity':'Error','tableId':a['id'],'rows':orphans,'title':'Composite foreign key has missing references','detail':str(len(orphans))+' child records have no full parent tuple.','ruleVersion':'1'})
    return result
