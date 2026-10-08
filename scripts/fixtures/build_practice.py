"""Create small fictional teaching sources with exact literals, then use the real importer."""
import base64,csv,io,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from importers import ingest
DATA={
 'amphibian': [('amphibian-events.csv',['event_id','date_literal','effort_minutes'],[['A01','2020-05-01','30'],['A02','2020-05-02','30'],['A03','2020-05-03','30']]),('amphibian-observations.csv',['record_id','event_id','recorded_name','count'],[['001','A01','Fictional frog A','0'],['002','A02','Fictional frog A','2'],['003','A02','Fictional frog B','1']])],
 'museum': [('specimens.csv',['catalog_number','recorded_name','collection_date','locality','label_code'],[['001','Fictional beetle A','03/04/01',' Cabinet A ','C1'],['1','Fictional beetle A','2001','Cabinet B','C1'],['002','','','Unknown','C9']]),('label-codebook.csv',['code','meaning','edition'],[['C1','Dry-mounted','2001'],['C1','Fluid-preserved','2005'],['C2','Slide-mounted','2001']])],
 'camera': [('deployments.csv',['deployment_id','start_literal','end_literal','effort_hours'],[['D01','2020-01-01','2020-01-02','24'],['D02','2020-01-02','2020-01-03','24']]),('media.csv',['media_id','deployment_id','timestamp_literal','file_path'],[['M01','D01','2020-01-01T08:00:00','fictional/M01.jpg'],['M02','D01','2020-01-01T09:00:00','fictional/M02.jpg'],['M03','D404','2020-01-02','fictional/M03.jpg']]),('observations.csv',['observation_id','media_id','recorded_name','count'],[['O01','M01','Fictional mammal A','1'],['O02','M02','','0'],['O03','M03','UNKNOWN','NA']])],
}
def main():
 out=ROOT/'examples/practice';out.mkdir(exist_ok=True);imports={}
 for kind,tables in DATA.items():
  folder=out/kind;folder.mkdir(exist_ok=True);items=[]
  for name,headers,rows in tables:
   text=io.StringIO(newline='');writer=csv.writer(text,lineterminator='\n');writer.writerow(headers);writer.writerows(rows);raw=text.getvalue().encode('utf-8');(folder/name).write_bytes(raw);items.append(ingest({'source':{'name':name,'base64':base64.b64encode(raw).decode()}}))
  text=('FICTIONAL PRACTICE ONLY. No actual specimens, surveys, locations or media.\n'
        'All scientific meanings start Unknown and must be reviewed explicitly.\n'
        'A recorded zero is distinct from a blank or NA literal.\n'
        'Dates remain literal; ambiguous order and precision must not be guessed.\n'
        '001 and 1 are distinct identifiers. Duplicate code meanings conflict.\n'
        'An event without observations can retain effort; the meaning needs protocol review.\n'
        'Camera file paths are fictional references; no image files are included.\n'
        'CC0-1.0 applies only to these authored fictional training inputs.\n').encode();(folder/'practice-notes.txt').write_bytes(text);items.append(ingest({'source':{'name':'practice-notes.txt','base64':base64.b64encode(text).decode()},'options':{'preserveOnly':True}}));imports[kind]=items
 (out/'imports.json').write_text(json.dumps(imports),encoding='utf-8')
if __name__=='__main__':main()
