"""Reproducible fictional recovery benchmark; traced Python memory is not RSS."""
import base64,json,sys,tempfile,time,tracemalloc
from pathlib import Path
from contextlib import closing
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from large_data import LargeStore
from large_preservation import package
from large_repair import preview,apply
from large_restore import Recovery
def run():
 with tempfile.TemporaryDirectory() as folder:
  root=Path(folder);store=LargeStore(root/'source');raw=('id,code\n'+''.join(f'{i:06d}, 0 \n' for i in range(10000))).encode();job=store.create('fictional-recovery-benchmark.csv',len(raw));id=job['id'];store.chunk(id,0,base64.b64encode(raw).decode());store.start(id,False);payload={'id':id,'columns':[1],'operation':'trim-whitespace'};apply(store,{**payload,**preview(store,payload),'reason':'Fictional benchmark whitespace only','reviewer':'Benchmark curator'});store.edit(id,1,action='undo',reason='Fictional benchmark batch undo');store.edit(id,2,action='redo',reason='Fictional benchmark batch redo');path=root/'package.zip'
  with package(store,id) as archive:path.write_bytes(archive.read())
  tracemalloc.start();started=time.perf_counter()
  with closing(Recovery(path)) as recovered:
   verified=time.perf_counter()-started;publish_started=time.perf_counter();status=recovered.publish(LargeStore(root/'target'),'Benchmark curator','Independent fictional recovery');published=time.perf_counter()-publish_started
  _,peak=tracemalloc.get_traced_memory();tracemalloc.stop();return {'build':'0.6.0-dev.6','fictionalRecords':10000,'replayedCellHistoryEntries':30000,'verifiedWorkingRevision':status['restoration']['workingRevision'],'verificationReplaySeconds':round(verified,3),'publicationSeconds':round(published,3),'peakTracedPythonBytes':peak,'measurementBoundary':'Python traced allocations only; excludes native SQLite and whole-process RSS. Timings describe this machine and fixture, not all-platform/full-scale acceptance.','allRecordsRetained':status['rows']==10000,'releaseComplete':False}
if __name__=='__main__':print(json.dumps(run(),indent=2))
