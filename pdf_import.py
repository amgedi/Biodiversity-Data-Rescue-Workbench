from worker_runtime import worker_command
"""Offline PDF evidence via a pinned parser in a bounded independent process."""
import hashlib,json,os,subprocess,sys,tempfile,threading
from pathlib import Path
from rescue import source_bytes
from pdf_limits import WindowsJob
ROOT=Path(__file__).resolve().parent
_slots=threading.BoundedSemaphore(2)
def verify_vendor():
 vendor=ROOT/'vendor';manifest=json.loads((vendor/'pypdf-manifest.json').read_text(encoding='utf-8'))
 if manifest.get('name')!='pypdf' or manifest.get('version')!='6.10.0':raise ValueError('PDF_READER_INTEGRITY')
 for name,facts in manifest['files'].items():
  path=vendor/name
  if not path.resolve().is_relative_to(vendor.resolve()) or path.is_symlink():raise ValueError('PDF_READER_INTEGRITY')
  raw=path.read_bytes()
  if len(raw)!=facts['bytes'] or hashlib.sha256(raw).hexdigest()!=facts['sha256']:raise ValueError('PDF_READER_INTEGRITY')
 expected=set(manifest['files']);actual={p.relative_to(vendor).as_posix() for p in vendor.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='pypdf-manifest.json'}
 if actual!=expected:raise ValueError('PDF_READER_INTEGRITY')
def recovered(data):
 if not _slots.acquire(blocking=False):return {'error':'PDF_BUSY'}
 process=None;job=None
 try:
  try:verify_vendor()
  except (ValueError,OSError,KeyError,TypeError):return {'error':'PDF_READER_INTEGRITY'}
  with tempfile.TemporaryDirectory(prefix='biorescue-pdf-') as directory:
   path=Path(directory)/'original.pdf';path.write_bytes(data);process=subprocess.Popen(worker_command('pdf_worker',path),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
   if os.name=='nt':
    try:job=WindowsJob(process)
    except OSError:
     process.kill();process.communicate();return {'error':'PDF_LIMIT_UNAVAILABLE'}
   try:output,_=process.communicate(input=b'go\n',timeout=20)
   except subprocess.TimeoutExpired:process.kill();process.communicate();return {'error':'PDF_TIMEOUT'}
   if process.returncode or len(output)>1024*1024:return {'error':'PDF_WORKER_FAILED'}
   result=json.loads(output)
   if not isinstance(result,dict):return {'error':'PDF_WORKER_FAILED'}
   return result
 except (ValueError,OSError,KeyError,TypeError):return {'error':'PDF_WORKER_FAILED'}
 finally:
  if process and process.poll() is None:process.kill();process.communicate()
  if job:job.close()
  _slots.release()
def pdf(source,options):
 result=recovered(source_bytes(source))
 if 'error' in result:preview={'kind':'pdf','blocks':[],'bounded':True,'reasonCode':result['error'],'notes':['Original PDF retained; no recovered text is asserted. No OCR or password workflow was attempted.']}
 else:preview=result
 return [],{'documentPreview':preview,'importReview':result['error'] if 'error' in result else None}
