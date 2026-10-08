"""Use the frozen engine's explicit worker dispatch without starting another server."""
import os,sys
from pathlib import Path
def worker_interpreter():
    # Windows virtual-environment python.exe is a redirector that starts another
    # process. Bounded readers allow one process, so invoke the real interpreter.
    # Reader workers use the standard library and our pinned vendored readers.
    if os.name=='nt' and sys.prefix!=sys.base_prefix:
        return sys._base_executable
    return sys.executable

def worker_command(name,path):
    if name not in {'pdf_worker','xls_worker','doc_worker','ocr_worker'}:raise ValueError('Unknown worker')
    if getattr(sys,'frozen',False):return [sys.executable,'--worker',name,str(path)]
    return [worker_interpreter(),'-X','utf8',str(Path(__file__).parent/(name+'.py')),str(path)]
