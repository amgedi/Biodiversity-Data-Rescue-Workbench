"""Use the frozen engine's explicit worker dispatch without starting another server."""
import sys
from pathlib import Path
def worker_command(name,path):
    if name not in {'pdf_worker','xls_worker','doc_worker','ocr_worker'}:raise ValueError('Unknown worker')
    if getattr(sys,'frozen',False):return [sys.executable,'--worker',name,str(path)]
    return [sys.executable,'-X','utf8',str(Path(__file__).parent/(name+'.py')),str(path)]
