"""Passive import inspection. Archives are never extracted onto the filesystem."""
import io, json, struct, zipfile
from pathlib import Path
from upgrades import safe_archive
from rescue import source_bytes
def archive(source,options):
    with safe_archive(source_bytes(source)) as z:
        return [],{'members':[{'name':i.filename,'bytes':i.file_size,'compressedBytes':i.compress_size,'crc32':f'{i.CRC:08x}'} for i in z.infolist()],'notes':['Container inventory only. No members executed or extracted; original archive preserved.']}
def geojson(source,options):
    from importers import table,literal
    value=json.loads(source_bytes(source).decode('utf-8-sig'))
    if value.get('type')!='FeatureCollection' or not isinstance(value.get('features'),list):raise ValueError('Only GeoJSON FeatureCollection supported.')
    features=value['features'];keys=[]
    for f in features:
        for k in (f.get('properties') or {}):
            if k not in keys:keys.append(k)
    reserved=['_feature_id','_geometry_json']
    if any(k in keys for k in reserved):raise ValueError('GeoJSON property conflicts with reserved extraction names.')
    rows=[keys+reserved]+[[literal((f.get('properties') or {}).get(k)) for k in keys]+[literal(f.get('id')),literal(f.get('geometry'))] for f in features]
    return [table(Path(source['name']).stem,rows,{'format':'geojson','headerRow':1})],{'notes':['Geometry retained as literal JSON; no CRS assumption, reprojection or inferred coordinate fields.'], 'foreignMembers':[k for k in value if k not in ['features','type']]}
def dbf(source,options):
    from importers import table
    data=source_bytes(source)
    if len(data)<33:raise ValueError('Truncated DBF header.')
    count,header,record=struct.unpack_from('<IHH',data,4)
    if count>100000 or header<33 or record<1 or header+count*record>len(data):raise ValueError('Invalid DBF dimensions or limit exceeded.')
    fields=[]
    for offset in range(32,header-1,32):
        if data[offset]==13:break
        d=data[offset:offset+32]
        if len(d)!=32:raise ValueError('Truncated DBF field descriptor.')
        fields.append({'name':d[:11].split(b'\0')[0].decode('ascii','replace'),'type':chr(d[11]),'length':d[16],'decimals':d[17]})
    if 1+sum(f['length'] for f in fields)!=record:raise ValueError('DBF record layout unsupported.')
    encoding=options.get('encoding','auto');encoding='cp1252' if encoding=='auto' else encoding
    rows=[[f['name'] for f in fields]+['_dbf_deleted']]
    for i in range(count):
        raw=data[header+i*record:header+(i+1)*record];pos=1;values=[]
        for f in fields:
            part=raw[pos:pos+f['length']];pos+=f['length']
            values.append(part.decode(encoding).rstrip(' ') if f['type'] in 'CNDLF' else 'hex:'+part.hex())
        rows.append(values+['true' if raw[:1]==b'*' else 'false'])
    return [table(Path(source['name']).stem,rows,{'format':'dbf','encoding':encoding,'headerRow':1})],{'fields':fields,'codePageByte':data[29],'notes':['Deleted records retained and flagged. Character/numeric/date values remain literal; memo/binary fields represented as hex pointers, associated memo files must be preserved separately. Auto encoding is Windows-1252, an explicit reviewable assumption.']}
