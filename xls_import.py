from worker_runtime import worker_command
"""Pinned, offline legacy XLS values; bounded worker never executes workbook code."""
import hashlib,json,os,subprocess,sys,tempfile,threading
from pathlib import Path
from pdf_limits import WindowsJob
from rescue import source_bytes
ROOT=Path(__file__).resolve().parent
_slots=threading.BoundedSemaphore(2)


def verify_vendor():
 root=ROOT/'vendor-xls';manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
 if manifest.get('name')!='xlrd' or manifest.get('version')!='2.0.2':raise ValueError('XLS_READER_INTEGRITY')
 expected=manifest['files'];actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='manifest.json'}
 if set(expected)!=actual:raise ValueError('XLS_READER_INTEGRITY')
 for name,facts in expected.items():
  path=root/name
  if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():raise ValueError('XLS_READER_INTEGRITY')
  raw=path.read_bytes()
  if len(raw)!=facts['bytes'] or hashlib.sha256(raw).hexdigest()!=facts['sha256']:raise ValueError('XLS_READER_INTEGRITY')


def recovered(data,options):
 if not _slots.acquire(blocking=False):return {'error':'XLS_BUSY'}
 process=None;job=None
 try:
  try:verify_vendor()
  except (ValueError,OSError,KeyError,TypeError):return {'error':'XLS_READER_INTEGRITY'}
  with tempfile.TemporaryDirectory(prefix='biorescue-xls-') as directory:
   path=Path(directory)/'original.xls';path.write_bytes(data)
   process=subprocess.Popen(worker_command('xls_worker',path),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
   if os.name=='nt':
    try:job=WindowsJob(process)
    except OSError:
     process.kill();process.communicate();return {'error':'XLS_LIMIT_UNAVAILABLE'}
   try:output,_=process.communicate(input=b'go\n'+json.dumps(options).encode('utf-8')+b'\n',timeout=20)
   except subprocess.TimeoutExpired:process.kill();process.communicate();return {'error':'XLS_TIMEOUT'}
   if process.returncode or len(output)>20*1024*1024:return {'error':'XLS_WORKER_FAILED'}
   result=json.loads(output)
   if not isinstance(result,dict):return {'error':'XLS_WORKER_FAILED'}
   return result
 except (ValueError,OSError,KeyError,TypeError):return {'error':'XLS_WORKER_FAILED'}
 finally:
  if process and process.poll() is None:process.kill();process.communicate()
  if job:job.close()
  _slots.release()


def xls(source,options):
 from importers import table
 reviewed={k:options[k] for k in ('headerRow','headersBySheet','encoding') if k in options}
 result=recovered(source_bytes(source),reviewed)
 if result.get('error'):return [],{'legacyExcel':{'conversionBlocked':True,'reasonCode':result['error']},'importReview':result['error']}
 archaeology=result['archaeology'];tables=[]
 for item in result['tables']:
  tables.append(table(item['name'],item['rows'],{'format':'xls','sheet':item['name'],'headerRow':item['headerRow'],'encoding':archaeology['encoding'],'dateSystem':archaeology['dateSystem'],'readerVersion':'xlrd-2.0.2','representation':'cached values; date serials unchanged; binary numbers round-trip'},[]))
 return tables,archaeology
