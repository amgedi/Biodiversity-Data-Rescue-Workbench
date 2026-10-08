import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
"""Reproducible local-only 500,000-record investigation benchmark."""
import base64,ctypes,json,os,time
from pathlib import Path
from large_data import LargeStore
root=Path(__file__).resolve().parents[2];folder=root/'examples/stress';folder.mkdir(exist_ok=True);source=folder/'survey-500000.csv'
with source.open('w',encoding='utf-8',newline='') as f:
 f.write('id,site,n,verbatim_date,note\n')
 for i in range(500000):f.write(f'{i:08d},S{i%100:03d},{i%99},2006-07,{"Fictional investigation record; convention unknown"}\n')
class Counters(ctypes.Structure):
 _fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong),('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t)]
def memory():
 if os.name!='nt':return None
 c=Counters();c.cb=ctypes.sizeof(c);ctypes.windll.kernel32.GetCurrentProcess.restype=ctypes.c_void_p;process=ctypes.windll.kernel32.GetCurrentProcess();fn=ctypes.windll.psapi.GetProcessMemoryInfo;fn.argtypes=[ctypes.c_void_p,ctypes.POINTER(Counters),ctypes.c_ulong];ok=fn(process,ctypes.byref(c),c.cb);return c.PeakWorkingSetSize if ok else None
large=LargeStore(root/'local-data/large');job=large.create(source.name,source.stat().st_size);offset=0;before=memory();started=time.perf_counter()
with source.open('rb') as f:
 while block:=f.read(1048576):large.chunk(job['id'],offset,base64.b64encode(block).decode());offset+=len(block)
upload=time.perf_counter()-started;started=time.perf_counter();status=large.start(job['id'],background=False);parse=time.perf_counter()-started
assert status['status']=='ready',status
started=time.perf_counter();page=large.page(job['id'],400000);paging=time.perf_counter()-started
started=time.perf_counter();filtered=large.page(job['id'],0,'S003');filtering=time.perf_counter()-started
started=time.perf_counter();size=sum(len(b) for b in large.export(job['id']));export=time.perf_counter()-started
assert status['rows']==500000 and len(page['rows'])==50 and filtered['total']==5000 and size==source.stat().st_size
result={'records':500000,'columns':5,'sourceBytes':source.stat().st_size,'uploadSeconds':upload,'incrementalHashParseProfileSeconds':parse,'pageAtRow400000Seconds':paging,'filterS003Seconds':filtering,'incrementalExportSeconds':export,'processPeakWorkingSetBytesBefore':before,'processPeakWorkingSetBytesAfter':memory(),'investigationId':job['id'],'measurementNotes':'One Windows run, hot local disk. Peak working set includes Python/runtime and page cache; not proof of a maximum. Rendering benchmark is separate. Export iterated without concatenating the full output.'}
(root/'docs').mkdir(exist_ok=True);(root/'docs/history/PERFORMANCE.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
