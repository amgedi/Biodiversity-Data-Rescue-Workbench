import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
"""Generate honest fictional source artifacts without needing spreadsheet software."""
import base64,io,json,struct,zipfile
from pathlib import Path
from importers import ingest
root=Path(__file__).resolve().parents[2];out=root/'examples'/'nightmare';out.mkdir(parents=True,exist_ok=True)
files={
'observations.csv':b'occurrence_id,survey_id,taxon,n,code,dt,lat,lon,mystery\nO1,E1,RAPI, 3 ,4,06/07/08,53.123456789,-113.25,8\nO1,E1,R. pipiens,999,4,39200,0,0,8\nO3,E404,Rana pipiens,NA,7,2006-02-30,-113,53,9\nO4,E2,northern leopard frog,0,4,2007-06,91,-113,?\n,E2,unknown,N/A,.,2010-06-12T10:00:00,53,-113,\nO6,E3,RAPI,-999,4,2011-06-12T10:00:00-06:00,10,120,\nO6,E3,RAPI,-999,4,2011-06-12T10:00:00-06:00,10,120,\n',
'events.csv':b'survey_id,site_id,effort_min,method\nE1,S1,10,visual encounter\nE2,S2,,visual encounter\nE2,S2,10,call survey\nE3,S3,20,call survey\nE4,S4,10,unknown\n',
'species_codes.csv':b'code,name,nameAccordingTo\nRAPI,Rana pipiens,Historical project list; authority unknown\nRAPI,R. pipiens,Unresolved abbreviation\nUNKNOWN,unknown,\n',
'weather.csv':b'survey_id,temp,temp_unit,rain\nE1,12,C,0\nE2,60,F,NA\nE3,999,unknown,-9\n',
'README_old.txt':b'FICTIONAL TRAINING EVIDENCE. README 2004: code 4 = juvenile. n is number of individuals visually encountered. NA denotes not recorded in observations. This does not establish meanings for other sentinel tokens. Datum and date convention not documented.\n',
'protocol_REVISED.txt':b'FICTIONAL TRAINING EVIDENCE. Protocol revision 2007, section 3: code 4 = unknown sex. It is unclear which annual file used this revision. n denotes observed individuals. Effort methodology changed to call surveys in 2007; comparability is unresolved.\n',
'field_notes.txt':'FICTIONAL: site S1 renamed "Creek East". Forêt notes copied from Windows-1252. The mystery field is unrecoverable. Some locations are deliberately marked sensitive.\n'.encode('cp1252'),
'sites.geojson':json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','properties':{'site_id':'S1','locality':'Fictional Creek East'},'geometry':{'type':'Point','coordinates':[-113.25,53.123456789]}}]}).encode()
}
def workbook(value):
 b=io.BytesIO()
 with zipfile.ZipFile(b,'w') as z:
  z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Survey" r:id="r1"/><sheet name="Clues" state="veryHidden" r:id="r2"/></sheets><definedNames><definedName name="Observations">Survey!$A$1:$B$2</definedName></definedNames></workbook>')
  z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/><Relationship Id="r2" Target="worksheets/sheet2.xml"/></Relationships>')
  z.writestr('xl/worksheets/sheet1.xml',f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>survey_id</t></is></c><c r="B1" t="inlineStr"><is><t>count</t></is></c></row><row r="2"><c r="A2" t="inlineStr"><is><t>E1</t></is></c><c r="B2"><f>1+2</f><v>{value}</v></c></row></sheetData></worksheet>')
  z.writestr('xl/worksheets/sheet2.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>note</t></is></c></row><row r="2"><c r="A2" t="inlineStr"><is><t>Cached formula differs between versions; source authority unknown.</t></is></c></row></sheetData></worksheet>')
  z.writestr('xl/worksheets/_rels/sheet1.xml.rels','<Relationships><Relationship Type="urn:example/comments" Target="../comments1.xml"/></Relationships>')
  z.writestr('xl/comments1.xml','<comments xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><authors><author>Fictional researcher</author></authors><commentList><comment ref="B2" authorId="0"><text><t>Visual count; cached field formula is unverified.</t></text></comment></commentList></comments>')
 return b.getvalue()
files['survey_FINAL.xlsx']=workbook(3);files['survey_FINAL2.xlsx']=files['survey_FINAL.xlsx'];files['survey_FINAL_FIXED.xlsx']=workbook(4)
# dBASE III plain character fields; deleted record retained for archaeology.
fields=[('site_id',8),('elev',8),('unit',8)];header=32+32*len(fields)+1;record=1+sum(width for _,width in fields);data=bytearray(header);data[0]=3;struct.pack_into('<IHH',data,4,3,header,record)
for i,(name,width) in enumerate(fields):offset=32+i*32;data[offset:offset+len(name)]=name.encode();data[offset+11]=ord('C');data[offset+16]=width
data[-1]=13
for deleted,values in [(False,['S1','750','m']),(False,['S2','2500','ft']),(True,['S3','-999','unknown'])]:data.extend(b'*' if deleted else b' ');data.extend(b''.join(v.encode().ljust(width,b' ') for v,(_,width) in zip(values,fields)))
files['sites.dbf']=bytes(data)+b'\x1a'
imports=[]
for name,data in files.items():
 (out/name).write_bytes(data);options={'preserveOnly':True} if name.endswith('.txt') else {}
 imports.append(ingest({'source':{'name':name,'base64':base64.b64encode(data).decode()},'options':options}))
(out/'imports.json').write_text(json.dumps(imports),encoding='utf-8')
print('Generated',len(files),'fictional sources')
