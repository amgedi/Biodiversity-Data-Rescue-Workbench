"""Keep one server process responsible for a workspace, regardless of HTTP port."""
import os
from pathlib import Path
class WorkspaceLock:
 def __init__(self,workspace):
  root=Path(workspace).resolve();root.mkdir(parents=True,exist_ok=True)
  self.file=(root/'.workspace-server.lock').open('a+b');self.file.seek(0)
  if os.fstat(self.file.fileno()).st_size==0:self.file.write(b'0');self.file.flush()
  self.file.seek(0)
  try:
   if os.name=='nt':
    import msvcrt
    msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
   else:
    import fcntl
    fcntl.flock(self.file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
  except OSError:
   self.file.close();raise ValueError('Another Workbench server owns this workspace. Use that server or choose a separate test workspace.')
 def close(self):
  if self.file.closed:return
  self.file.seek(0)
  if os.name=='nt':
   import msvcrt
   msvcrt.locking(self.file.fileno(),msvcrt.LK_UNLCK,1)
  else:
   import fcntl
   fcntl.flock(self.file.fileno(),fcntl.LOCK_UN)
  self.file.close()
 def __enter__(self):return self
 def __exit__(self,*args):self.close()
