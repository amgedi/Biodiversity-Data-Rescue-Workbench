"""Bounded temporary package uploads; verification precedes reviewed publication."""
import atexit,base64,hashlib,shutil,tempfile,threading,time,uuid
from large_paired_restore import open_recovery
class RestoreUploads:
 def __init__(self,clock=time.monotonic):self.clock=clock;self.entries={};self.lock=threading.RLock();atexit.register(self.close)
 def dispose(self,entry):
  if entry.get('recovery'):entry['recovery'].close()
  entry['temporary'].cleanup()
 def cleanup(self):
  for token,entry in list(self.entries.items()):
   if self.clock()-entry['at']>900:self.dispose(self.entries.pop(token))
 def get(self,token):
  self.cleanup()
  if not isinstance(token,str) or token not in self.entries:raise ValueError('LARGE_RESTORE_EXPIRED')
  return self.entries[token]
 def create(self,size):
  if type(size) is not int or not 0<size<=512*1024*1024:raise ValueError('LARGE_RESTORE_LIMIT')
  with self.lock:
   self.cleanup()
   if len(self.entries)>=2:raise ValueError('LARGE_RESTORE_BUSY')
   temporary=tempfile.TemporaryDirectory(prefix='biorescue-package-upload-');token=str(uuid.uuid4());self.entries[token]={'temporary':temporary,'path':__import__('pathlib').Path(temporary.name)/'package.zip','expected':size,'received':0,'at':self.clock(),'recovery':None};return {'token':token,'receivedBytes':0}
 def chunk(self,token,offset,data):
  with self.lock:
   entry=self.get(token)
   if type(offset) is not int or offset!=entry['received'] or entry['recovery']:raise ValueError('LARGE_RESTORE_OFFSET')
   try:raw=base64.b64decode(data,validate=True)
   except (ValueError,TypeError):raise ValueError('LARGE_RESTORE_OFFSET') from None
   if not 0<len(raw)<=1024*1024 or offset+len(raw)>entry['expected']:raise ValueError('LARGE_RESTORE_OFFSET')
   with entry['path'].open('ab') as target:target.write(raw)
   entry['received']+=len(raw);entry['at']=self.clock();return {'receivedBytes':entry['received']}
 def preview(self,token,password=None):
  with self.lock:
   entry=self.get(token)
   if entry['received']!=entry['expected']:raise ValueError('LARGE_RESTORE_INCOMPLETE')
   if not entry['recovery']:
    from large_encryption import encrypted,decrypt
    path=entry['path'];encryption=None
    if encrypted(path):
     with path.open('rb') as source:
      digest=hashlib.sha256()
      while chunk:=source.read(65536):digest.update(chunk)
     plaintext,encryption=decrypt(path,password)
     path=path.parent/'authenticated-package.zip'
     with plaintext,path.open('wb') as target:shutil.copyfileobj(plaintext,target,65536)
     encryption['encryptedPackageSha256']=digest.hexdigest()
    entry['recovery']=open_recovery(path)
    if encryption:entry['recovery'].report['encryption']=encryption
   entry['at']=self.clock();return entry['recovery'].report
 def publish(self,token,target,digest,reviewer,reason):
  with self.lock:
   entry=self.get(token);recovery=entry['recovery']
   if not recovery or digest!=recovery.report['packageSha256']:raise ValueError('LARGE_RESTORE_PREVIEW')
   result=recovery.publish(target,reviewer,reason);self.dispose(self.entries.pop(token));return result
 def cancel(self,token):
  with self.lock:
   self.dispose(self.entries.pop(token)) if token in self.entries else None
   return {'cancelled':True}
 def close(self):
  with self.lock:
   for entry in self.entries.values():self.dispose(entry)
   self.entries.clear()
def registry(server):
 with _lock:
  if not hasattr(server,'restore_uploads'):server.restore_uploads=RestoreUploads()
  return server.restore_uploads
_lock=threading.Lock()
