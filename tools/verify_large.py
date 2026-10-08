"""Record-by-record verification using an isolated temporary investigation.
Usage: python tools/verify_large.py path/to/fictional.csv
Never opens or changes existing application investigations.
"""
import base64,csv,hashlib,io,json,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from large_data import LargeStore

def verify(source):
    with tempfile.TemporaryDirectory(prefix='biorescue-verification-') as folder:
        store=LargeStore(folder);job=store.create(source.name,source.stat().st_size)
        start=time.perf_counter();digest=hashlib.sha256();offset=0
        with source.open('rb') as stream:
            while chunk:=stream.read(1024*1024):
                digest.update(chunk);store.chunk(job['id'],offset,base64.b64encode(chunk).decode());offset+=len(chunk)
        store.start(job['id'],False);state=store.status(job['id'])
        if state['status']!='ready':raise ValueError(state)
        elapsed=time.perf_counter()-start;row=min(400001,state['rows']);column=2
        before=store.page(job['id'],offset=row-1,limit=1)['rows'][0]['values'][column]
        value='42' if before!='42' else '43';start=time.perf_counter()
        store.edit(job['id'],0,row,column,value,before,'Isolated reproducibility verification')
        edit_elapsed=time.perf_counter()-start
        store.edit(job['id'],1,reason='Verify undo',action='undo');store.edit(job['id'],2,reason='Verify redo',action='redo')
        start=time.perf_counter();export_path=Path(folder)/'verified.csv'
        with export_path.open('wb') as out:
            for chunk in store.export(job['id']):out.write(chunk)
        count=0
        with source.open(encoding='utf-8-sig',newline='') as original,export_path.open(encoding='utf-8-sig',newline='') as exported:
            a=csv.reader(original);b=csv.reader(exported);assert next(a)==next(b)
            for n,record in enumerate(a,1):
                expected=list(record)
                if n==row:expected[column]=value
                assert next(b)==expected,('Record mismatch',n)
                count+=1
            assert next(b,None) is None
        with (store.folder(job['id'])/'original.bin').open('rb') as original:
            original_hash=hashlib.file_digest(original,'sha256').hexdigest()
        assert original_hash==digest.hexdigest()
        return dict(rows=count,bytes=offset,parseAndChunkSeconds=elapsed,singleEditSeconds=edit_elapsed,streamExportAndCompareSeconds=time.perf_counter()-start,unchangedRecordsVerified=count-1,originalSHA256Verified=True,undoRedoVerified=True)

if __name__=='__main__':print(json.dumps(verify(Path(sys.argv[1]).resolve()),indent=2))
