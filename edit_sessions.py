"""Ephemeral editing authority complements durable scientific revision checks."""
import secrets,time
from contextlib import contextmanager
from datetime import datetime,timezone
from storage import LOCK

class EditSessions:
    def __init__(self,clock=time.monotonic,ttl=45):
        self.clock=clock;self.ttl=ttl;self.entries={};self.generations={}
    def _active(self,pid):
        entry=self.entries.get(pid)
        if entry and entry['expires']<=self.clock():self.entries.pop(pid,None);return None
        return entry
    def _reply(self,pid,entry,editing=False):
        result={'projectId':pid,'editing':editing,'generation':self.generations.get(pid,0),'expiresInSeconds':self.ttl if entry else 0,'timestamp':datetime.now(timezone.utc).isoformat()}
        if entry:result['ownerSession']=entry['session']
        if editing:result['token']=entry['token']
        return result
    def claim(self,pid,session,force=False,expected=None):
        if not isinstance(session,str) or not 8<=len(session)<=100:raise ValueError('EDIT_SESSION_REQUIRED')
        with LOCK:
            entry=self._active(pid)
            if entry and entry['session']!=session:
                if not force:return self._reply(pid,entry)
                if expected!=self.generations.get(pid,0):raise ValueError('EDIT_TAKEOVER_CONFLICT')
            if not entry or entry['session']!=session:
                self.generations[pid]=self.generations.get(pid,0)+1
                entry={'session':session,'token':secrets.token_urlsafe(32),'expires':self.clock()+self.ttl};self.entries[pid]=entry
            entry['expires']=self.clock()+self.ttl
            return self._reply(pid,entry,True)
    def check(self,pid,session=None,token=None):
        with LOCK:
            entry=self._active(pid)
            # Legacy clients may write only while no window holds editing authority.
            if not entry:
                if session or token:raise ValueError('EDIT_SESSION_EXPIRED')
                return
            if session!=entry['session'] or not isinstance(token,str) or not secrets.compare_digest(token,entry['token']):raise ValueError('EDIT_AUTHORITY_LOST')
    def renew(self,pid,session,token):
        with LOCK:
            self.check(pid,session,token);entry=self._active(pid)
            if not entry:raise ValueError('EDIT_SESSION_EXPIRED')
            entry['expires']=self.clock()+self.ttl
            return self._reply(pid,entry,True)
    def release(self,pid,session,token):
        with LOCK:
            self.check(pid,session,token);self.entries.pop(pid,None)
            return self._reply(pid,None)

def registry(server):
    with LOCK:
        if not hasattr(server,'edit_sessions'):server.edit_sessions=EditSessions()
        return server.edit_sessions

def write_project_id(path,payload):
    if path in ['/api/large-link-save','/api/large-batch-trim','/api/large-metadata','/api/large-edit','/api/large-chunk','/api/large-start','/api/large-cancel']:return 'large:'+payload.get('id','')
    if path=='/api/workspace-state':return payload.get('projectId')
    if path in ['/api/save']:return payload.get('id')
    if path in ['/api/draft','/api/migrate']:return payload.get('projectId') or payload.get('project',{}).get('id') or payload.get('id')
    if path in ['/api/snapshot']:return payload.get('project',{}).get('id')
    if path in ['/api/project-action'] and payload.get('action') in ['rename','archive','trash','snapshot']:return payload.get('id')
    if path=='/api/project-delete':return payload.get('id')
    return None

@contextmanager
def authorized_write(server,pid,session,token):
    if not pid:
        yield
        return
    # Authority and scientific mutation use the same lock; takeover cannot race between them.
    with LOCK:
        registry(server).check(pid,session,token)
        yield
