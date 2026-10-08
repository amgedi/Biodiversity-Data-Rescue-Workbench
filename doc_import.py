from worker_runtime import worker_command
"""Pinned offline OLE container and bounded MS-DOC text evidence worker."""
import json,os,subprocess,sys,tempfile,threading
from pathlib import Path
from pdf_limits import WindowsJob
from rescue import source_bytes
from xls_import import verify_vendor
ROOT=Path(__file__).resolve().parent
_slots=threading.BoundedSemaphore(2)

def recovered(data):
 if len(data)>20*1024*1024:return {'error':'DOC_LIMIT'}
 if not _slots.acquire(blocking=False):return {'error':'DOC_BUSY'}
 process=None;job=None
 try:
  try:verify_vendor()
  except (ValueError,OSError,KeyError,TypeError):return {'error':'DOC_READER_INTEGRITY'}
  with tempfile.TemporaryDirectory(prefix='biorescue-doc-') as directory:
   path=Path(directory)/'original.doc';path.write_bytes(data)
   process=subprocess.Popen(worker_command('doc_worker',path),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
   if os.name=='nt':
    try:job=WindowsJob(process)
    except OSError:
     process.kill();process.communicate();return {'error':'DOC_LIMIT_UNAVAILABLE'}
   try:output,_=process.communicate(input=b'go\n',timeout=20)
   except subprocess.TimeoutExpired:process.kill();process.communicate();return {'error':'DOC_TIMEOUT'}
   if process.returncode or len(output)>4*1024*1024:return {'error':'DOC_WORKER_FAILED'}
   result=json.loads(output)
   if not isinstance(result,dict):return {'error':'DOC_WORKER_FAILED'}
   return result
 except (ValueError,OSError,KeyError,TypeError):return {'error':'DOC_WORKER_FAILED'}
 finally:
  if process and process.poll() is None:process.kill();process.communicate()
  if job:job.close()
  _slots.release()

def doc(source,options):
 result=recovered(source_bytes(source))
 if 'error' in result:preview={'kind':'legacy-doc','blocks':[],'bounded':True,'reasonCode':result['error']}
 else:preview=result
 return [],{'documentPreview':preview,'importReview':result.get('error')}
