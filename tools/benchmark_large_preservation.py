"""Reproducible fictional-data benchmark; no private workspace access."""
import base64,json,tempfile,time,tracemalloc
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from large_data import LargeStore
from large_repair import preview,apply
from large_preservation import package
from tools.verify_large_package import verify

def run(rows=10000):
 with tempfile.TemporaryDirectory() as temporary:
  store=LargeStore(temporary);raw=('id,note,count\n'+''.join(f' {i:06d} , fictional ,0\n' for i in range(rows))).encode();job=store.create('fictional-performance.csv',len(raw));id=job['id'];store.chunk(id,0,base64.b64encode(raw).decode());store.start(id,False);payload={'id':id,'columns':[0,1],'operation':'trim-whitespace'};tracemalloc.start();start=time.perf_counter();proposal=preview(store,payload);preview_seconds=time.perf_counter()-start;start=time.perf_counter();apply(store,{**payload,**proposal,'reason':'Reproducible fictional benchmark only.','reviewer':'Fictional benchmark curator'});commit_seconds=time.perf_counter()-start;start=time.perf_counter();path=Path(temporary)/'preservation.zip'
  with package(store,id) as archive,path.open('wb') as target:
   while chunk:=archive.read(65536):target.write(chunk)
  package_seconds=time.perf_counter()-start;peak=tracemalloc.get_traced_memory()[1];tracemalloc.stop();verified=verify(path)
  return {'fictionalRows':rows,'changedCells':proposal['changedCells'],'previewSeconds':preview_seconds,'commitSeconds':commit_seconds,'packageSeconds':package_seconds,'pythonAllocationPeakBytes':peak,'memoryMeasurement':'Python traced allocations for preview/commit/package only; not whole-process RSS or SQLite/native allocations.','packageBytes':path.stat().st_size,'verification':verified}

if __name__=='__main__':print(json.dumps(run(),indent=2))
