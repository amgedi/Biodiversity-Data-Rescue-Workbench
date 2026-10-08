"""Bounded, expiring file-backed native downloads; no scientific/workspace writes."""
import atexit,threading,time,uuid
class TemporaryExports:
 def __init__(self,clock=time.monotonic,ttl=300):self.clock=clock;self.ttl=ttl;self.lock=threading.RLock();self.files={};self.pending=set();atexit.register(self.close)
 def expire(self):
  for token,item in list(self.files.items()):
   if item['expires']<=self.clock():item['file'].close();del self.files[token]
 def create(self,factory):
  token=str(uuid.uuid4())
  with self.lock:
   self.expire()
   if len(self.files)+len(self.pending)>=3:raise ValueError('LARGE_LINK_DOWNLOAD_BUSY')
   self.pending.add(token)
  artifact=None
  try:
   artifact=factory();artifact.seek(0,2);size=artifact.tell();artifact.seek(0)
   with self.lock:
    self.expire()
    if size+sum(item['bytes'] for item in self.files.values())>1024**3:raise ValueError('LARGE_LINK_DOWNLOAD_BUSY')
    self.files[token]={'file':artifact,'bytes':size,'expires':self.clock()+self.ttl};artifact=None
   return {'token':token,'bytes':size,'expiresInSeconds':self.ttl}
  finally:
   with self.lock:self.pending.discard(token)
   if artifact is not None:artifact.close()
 def take(self,token):
  with self.lock:
   self.expire();item=self.files.pop(token,None)
   if item is None:raise ValueError('LARGE_LINK_DOWNLOAD_EXPIRED')
   return item
 def close(self):
  with self.lock:
   for item in self.files.values():item['file'].close()
   self.files.clear()
_registry_lock=threading.Lock()
def registry(server):
 with _registry_lock:
  if not hasattr(server,'temporary_exports'):server.temporary_exports=TemporaryExports()
  return server.temporary_exports
