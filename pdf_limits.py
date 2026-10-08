"""Operating-system process limits, established before the PDF parser starts."""
import os
MEMORY=256*1024*1024
class WindowsJob:
 def __init__(self,process,memory=MEMORY,active=1,job_memory=False):
  import ctypes
  from ctypes import wintypes as w
  class Basic(ctypes.Structure):_fields_=[('processTime',ctypes.c_longlong),('jobTime',ctypes.c_longlong),('flags',w.DWORD),('minimum',ctypes.c_size_t),('maximum',ctypes.c_size_t),('active',w.DWORD),('affinity',ctypes.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
  class IO(ctypes.Structure):_fields_=[('readOperations',ctypes.c_ulonglong),('writeOperations',ctypes.c_ulonglong),('otherOperations',ctypes.c_ulonglong),('readBytes',ctypes.c_ulonglong),('writeBytes',ctypes.c_ulonglong),('otherBytes',ctypes.c_ulonglong)]
  class Extended(ctypes.Structure):_fields_=[('basic',Basic),('io',IO),('processMemory',ctypes.c_size_t),('jobMemory',ctypes.c_size_t),('peakProcess',ctypes.c_size_t),('peakJob',ctypes.c_size_t)]
  kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,w.LPCWSTR];kernel.CreateJobObjectW.restype=w.HANDLE;kernel.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD];kernel.SetInformationJobObject.restype=w.BOOL;kernel.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE];kernel.AssignProcessToJobObject.restype=w.BOOL;kernel.CloseHandle.argtypes=[w.HANDLE];kernel.CloseHandle.restype=w.BOOL;self.kernel=kernel;self.handle=kernel.CreateJobObjectW(None,None)
  if not self.handle:raise OSError('PDF_LIMIT_UNAVAILABLE')
  settings=Extended();settings.basic.flags=0x00000100|0x00002000|0x00000008;settings.basic.active=active;settings.processMemory=memory
  if job_memory:settings.basic.flags|=0x00000200;settings.jobMemory=memory
  if not kernel.SetInformationJobObject(self.handle,9,ctypes.byref(settings),ctypes.sizeof(settings)) or not kernel.AssignProcessToJobObject(self.handle,int(process._handle)):
   self.close();raise OSError('PDF_LIMIT_UNAVAILABLE')
 def close(self):
  if getattr(self,'handle',None):self.kernel.CloseHandle(self.handle);self.handle=None
def child_limits():
 if os.name=='nt':return 'Windows job: 256 MiB committed process memory, one process, termination when job handle closes.'
 try:
  import resource
  resource.setrlimit(resource.RLIMIT_AS,(MEMORY,MEMORY));resource.setrlimit(resource.RLIMIT_CPU,(20,20));return 'POSIX 256 MiB address-space limit and 20-second CPU limit.'
 except (ImportError,ValueError,OSError):raise ValueError('PDF_LIMIT_UNAVAILABLE') from None
