import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
"""Build synthetic input files and prepare importer output for the JS project model."""
import base64
import csv
import json
from pathlib import Path
from importers import ingest

ROOT=Path(__file__).resolve().parents[2]
DATA={
    'events':(['event_id','site','effort_min','dt'],[['E01','North woods','30','05/06/2008'],['E02',' Creek bend ','20','2008-06-07'],['E03','South meadow','','2008']]),
    'taxa':(['taxon_code','scientific_name','common_name'],[['T1','Turdus migratorius','American robin'],['T2','Poecile atricapillus','Black-capped chickadee'],['T3','Pica hudsonia','Black-billed magpie']]),
    'obs':(['record_id','event_id','taxon_code','n','lat','lon','dt','code'],[['001','E01','T1',' 3 ','53.54','-113.49','05/06/2008','A'],['002','E01','T2','NA','53.55','-113.50','2008-06-05','B'],['003','E02','UNKNOWN','two','153.56','53.56','2008-02-30','?'],['004','E02','T3','2','0','0','2008-06','A'],['004','E02','T3','2','0','0','2008-06','A'],['005','E404','','0','-9999','9999','06/07/2008','-']]),
}
if __name__=='__main__':
    examples=ROOT/'examples';work=ROOT/'work';work.mkdir(exist_ok=True)
    imports=[]
    for name,(headers,rows) in DATA.items():
        path=examples/(name+'_2008.csv')
        with path.open('w',encoding='utf-8',newline='') as f:w=csv.writer(f,lineterminator='\n');w.writerow(headers);w.writerows(rows)
        imports.append(ingest({'source':{'name':path.name,'base64':base64.b64encode(path.read_bytes()).decode()}}))
    path=examples/'protocol_2008.txt';imports.append(ingest({'source':{'name':path.name,'base64':base64.b64encode(path.read_bytes()).decode()},'options':{'preserveOnly':True}}))
    (work/'demo-imports.json').write_text(json.dumps(imports,ensure_ascii=False),encoding='utf-8')
    print('Prepared fictional CSVs and protocol evidence. Run node build_demo.mjs next.')
