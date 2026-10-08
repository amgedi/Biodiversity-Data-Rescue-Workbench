"""Bounded CSV ingestion into SQLite, incrementally hashed originals and paged access.
This investigation store deliberately does not reuse in-memory repair snapshots.
"""
import base64, csv, hashlib, io, json, os, sqlite3, threading, time, uuid
from collections import Counter
from contextlib import closing
from pathlib import Path
from upgrades import atomic, now
from storage import ID
csv.field_size_limit(1024*1024)
class LargeStore:
    def __init__(self,root):self.root=Path(root);self.jobs={};self.lock=threading.RLock()
    def folder(self,id):
        if not ID.fullmatch(id):raise ValueError('Invalid investigation ID.')
        return self.root/id
    def create(self,name,size,encoding='utf-8-sig',delimiter=','):
        if not isinstance(size,int) or not 0<size<=256*1024*1024:raise ValueError('Streaming investigation limit: 256 MiB.')
        if encoding not in ['utf-8','utf-8-sig','cp1252','latin-1','utf-16']:raise ValueError('Unsupported encoding.')
        if delimiter not in [',',';','\t','|']:raise ValueError('Choose an explicit supported delimiter.')
        with self.lock:
            if any(j.get('status') in ['uploading','parsing'] for j in self.jobs.values()):raise ValueError('One streaming investigation at a time; finish or cancel the current operation.')
            id=str(uuid.uuid4());folder=self.folder(id);folder.mkdir(parents=True)
            job={'storageVersion':2,'id':id,'name':str(name)[:200],'expectedBytes':size,'receivedBytes':0,'rows':0,'encoding':encoding,'delimiter':delimiter,'status':'uploading','startedAt':now(),'cancel':False}
            self.jobs[id]=job;atomic(folder/'status.json',job);return dict(job)
    def chunk(self,id,offset,data):
        with self.lock:
            j=self.jobs[id]
            if j['status']!='uploading' or offset!=j['receivedBytes']:raise ValueError('Upload offset/state conflict; preserve the source and restart.')
            raw=base64.b64decode(data,validate=True)
            if not raw or len(raw)>1024*1024 or offset+len(raw)>j['expectedBytes']:raise ValueError('Invalid chunk size.')
            with (self.folder(id)/'upload.part').open('ab') as f:f.write(raw)
            j['receivedBytes']+=len(raw);return {'receivedBytes':j['receivedBytes']}
    def start(self,id,background=True):
        j=self.jobs[id]
        if j['status']!='uploading' or j['receivedBytes']!=j['expectedBytes']:raise ValueError('Upload incomplete.')
        j['status']='parsing';atomic(self.folder(id)/'status.json',j)
        if background:threading.Thread(target=self.parse,args=(id,),daemon=True).start()
        else:self.parse(id)
        return self.status(id)
    def cancel(self,id):
        j=self.jobs[id];j['cancel']=True
        if j['status']=='uploading':j['status']='cancelled';atomic(self.folder(id)/'status.json',j)
        return dict(j)
    def status(self,id):
        if id in self.jobs:return {k:v for k,v in self.jobs[id].items() if k!='cancel'}
        value=json.loads((self.folder(id)/'status.json').read_text(encoding='utf-8'))
        group=value.get('restoration',{}).get('groupId')
        if group:
            if not isinstance(group,str) or not ID.fullmatch(group):raise ValueError('LARGE_RESTORE_GROUP_INCOMPLETE')
            try:
                catalog=self.root/'restore-groups'/(group+'.json')
                if catalog.stat().st_size>20000:raise ValueError('LARGE_RESTORE_GROUP_INCOMPLETE')
                manifest=json.loads(catalog.read_text(encoding='utf-8'))
                ids=manifest.get('ids')
                if manifest.get('version')!=1 or manifest.get('groupId')!=group or not isinstance(ids,list) or len(ids)!=2 or len(set(ids))!=2 or id not in ids or any(not isinstance(other,str) or not ID.fullmatch(other) for other in ids):raise ValueError('LARGE_RESTORE_GROUP_INCOMPLETE')
                for other in ids:
                    member=json.loads((self.folder(other)/'status.json').read_text(encoding='utf-8'))
                    if member.get('restoration',{}).get('groupId')!=group or member.get('status')!='ready':raise ValueError('LARGE_RESTORE_GROUP_INCOMPLETE')
            except (OSError,KeyError,TypeError,json.JSONDecodeError):raise ValueError('LARGE_RESTORE_GROUP_INCOMPLETE') from None
        if value['status'] in ['uploading','parsing']:
            value['status']='interrupted';value['error']='Server stopped before completion. Partial bytes retained; re-import the source.'
            path=self.folder(id)/'upload.part'
            if path.exists():value['receivedBytes']=path.stat().st_size
        return value
    def list(self):
        if not self.root.exists():return []
        result=[]
        for folder in self.root.iterdir():
            if not folder.is_dir() or folder.name.startswith('.') or not (folder/'status.json').exists():continue
            try:result.append(self.status(folder.name))
            except ValueError as error:
                if str(error)!='LARGE_RESTORE_GROUP_INCOMPLETE':raise
        return result
    def interrupted_restores(self):
        """Read-only, bounded inventory; never complete or delete a partial pair."""
        result=[];scanned=0;truncated=False
        if not self.root.exists():return {'items':result,'truncated':False,'scanned':0}
        with self.lock:
            for folder in self.root.iterdir():
                if scanned>=1000:truncated=True;break
                scanned+=1
                if not folder.is_dir() or folder.is_symlink():continue
                staged=folder.name.startswith(('.restore-','.paired-')) and folder.name.endswith('.pending')
                statuspath=folder/'status.json'
                if staged:
                    result.append({'directory':folder.name,'state':'staged','originalRetained':(folder/'original.bin').is_file(),'action':'Preserve this directory and the input package. Reverify and restore the package as a separate pair; no automatic publication or deletion.'})
                    continue
                if folder.name.startswith('.') or not ID.fullmatch(folder.name) or not statuspath.is_file():continue
                try:
                    if statuspath.stat().st_size>1024*1024:continue
                    value=json.loads(statuspath.read_text(encoding='utf-8'))
                    group=value.get('restoration',{}).get('groupId')
                    if not group:continue
                    try:self.status(folder.name)
                    except ValueError as error:
                        if str(error)!='LARGE_RESTORE_GROUP_INCOMPLETE':raise
                        result.append({'directory':folder.name,'groupId':group,'state':'incomplete-pair','originalRetained':(folder/'original.bin').is_file(),'action':'Both investigations are unavailable until a complete reviewed pair is restored. Preserve these retained files and reverify the input package; no automatic publication or deletion.'})
                except (OSError,TypeError,AttributeError,json.JSONDecodeError):
                    result.append({'directory':folder.name,'state':'unreadable-status','originalRetained':(folder/'original.bin').is_file(),'action':'Retain the directory and inspect status corruption before recovery. No automatic changes.'})
        return {'items':result,'truncated':truncated,'scanned':scanned}
    def parse(self,id):
        j=self.jobs[id];folder=self.folder(id);start=time.perf_counter();conn=None
        try:
            digest=hashlib.sha256()
            with (folder/'upload.part').open('rb') as f:
                while block:=f.read(1024*1024):
                    if j['cancel']:raise InterruptedError('Cancelled during hashing.')
                    digest.update(block)
            j['sha256']=digest.hexdigest()
            os.replace(folder/'upload.part',folder/'original.bin')
            conn=sqlite3.connect(folder/'rows.sqlite');conn.execute('PRAGMA journal_mode=WAL');conn.execute('CREATE TABLE rows (id INTEGER PRIMARY KEY, data TEXT NOT NULL)')
            with (folder/'original.bin').open('r',encoding=j['encoding'],newline='') as f:
                reader=csv.reader(f,delimiter=j['delimiter'],strict=True);raw=next(reader)
                if not raw or len(raw)>250:raise ValueError('Header must contain 1–250 columns.')
                headers=[]
                for c,h in enumerate(raw):
                    h=h.strip() or f'column_{c+1}';base=h;k=2
                    while h in headers:h=f'{base}_{k}';k+=1
                    headers.append(h)
                j['headers']=headers;j['originalHeaders']=raw
                stats=[{'empty':0,'minLength':None,'maxLength':0,'whitespace':0,'numericCount':0,'numericMin':None,'numericMax':None,'samples':[]} for _ in headers]
                batch=[]
                for i,row in enumerate(reader,1):
                    if j['cancel']:raise InterruptedError('Cancelled during parsing; original retained.')
                    if i>2000000:raise ValueError('Investigation limit: 2 million records.')
                    if len(row)!=len(headers):raise ValueError(f'Row {i+1} has {len(row)} fields; expected {len(headers)}. Reinspect in normal rescue mode. No padding/truncation applied.')
                    for c,v in enumerate(row):
                        s=stats[c];s['empty']+=not v;s['whitespace']+=v!=v.strip();s['maxLength']=max(s['maxLength'],len(v));s['minLength']=len(v) if s['minLength'] is None else min(s['minLength'],len(v))
                        if v and v not in s['samples'] and len(s['samples'])<5:s['samples'].append(v[:200])
                        try:
                            n=float(v)
                            import math
                            if math.isfinite(n):s['numericCount']+=1;s['numericMin']=n if s['numericMin'] is None else min(n,s['numericMin']);s['numericMax']=n if s['numericMax'] is None else max(n,s['numericMax'])
                        except ValueError:pass
                    batch.append((json.dumps(row,ensure_ascii=False),))
                    if len(batch)>=1000:conn.executemany('INSERT INTO rows(data) VALUES (?)',batch);conn.commit();batch=[];j['rows']=i
                if batch:conn.executemany('INSERT INTO rows(data) VALUES (?)',batch);conn.commit()
                j['rows']=i if 'i' in locals() else 0;j['profile']=stats
            j['status']='ready';j['seconds']=round(time.perf_counter()-start,3)
        except (Exception,) as exc:j['status']='cancelled' if isinstance(exc,InterruptedError) else 'failed';j['error']=str(exc)
        finally:
            if conn:conn.close()
            atomic(folder/'status.json',{k:v for k,v in j.items() if k!='cancel'})
    def page(self,id,offset=0,query='',limit=50):
        j=self.status(id)
        if j['status']!='ready':raise ValueError('Investigation is not complete.')
        if not isinstance(limit,int) or not 1<=limit<=100:raise ValueError('Page size must be 1–100.')
        if not 0<=offset<=j['rows'] or len(query)>200:raise ValueError('Invalid page/query.')
        needle=json.dumps(query,ensure_ascii=False)[1:-1].replace('\\','\\\\').replace('%','\\%').replace('_','\\_');term='%'+needle+'%'
        with closing(self.edit_connection(id)) as conn:
            conn.execute('BEGIN')
            revision=conn.execute("SELECT value FROM edit_meta WHERE key='revision'").fetchone()[0]
            count=conn.execute("SELECT count(*) FROM rows WHERE data LIKE ? ESCAPE '\\'",(term,)).fetchone()[0] if query else j['rows']
            rows=conn.execute("SELECT id,data FROM rows WHERE data LIKE ? ESCAPE '\\' ORDER BY id LIMIT ? OFFSET ?",(term,limit,offset)).fetchall() if query else conn.execute('SELECT id,data FROM rows ORDER BY id LIMIT ? OFFSET ?',(limit,offset)).fetchall()
        return {'headers':j['headers'],'rows':[{'row':i,'values':json.loads(v)} for i,v in rows],'total':count,'offset':offset,'revision':revision,'limit':limit,'note':'Literal text search; no ecological interpretation.'}
    def export(self,id):
        self.edit_state(id) # Establish WAL/history before opening a long read snapshot.
        j=self.status(id)
        if j['status']!='ready':raise ValueError('Investigation is not complete.')
        buf=io.StringIO(newline='');writer=csv.writer(buf,lineterminator='\n');writer.writerow(j['headers']);yield buf.getvalue().encode('utf-8');buf.seek(0);buf.truncate()
        with closing(sqlite3.connect(self.folder(id)/'rows.sqlite')) as conn:
            conn.execute('BEGIN')
            for (data,) in conn.execute('SELECT data FROM rows ORDER BY id'):
                writer.writerow(json.loads(data))
                if buf.tell()>65536:yield buf.getvalue().encode('utf-8');buf.seek(0);buf.truncate()
            if buf.tell():yield buf.getvalue().encode('utf-8')

    def edit_connection(self,id):
        if self.status(id)['status']!='ready':raise ValueError('Investigation is not complete.')
        conn=sqlite3.connect(self.folder(id)/'rows.sqlite',timeout=20)
        try:
            if self.status(id).get('storageVersion',1)<2 and not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='edit_meta'").fetchone():
                backup=self.folder(id)/'pre-v04-rows.sqlite'
                if not backup.exists():
                    temporary=self.folder(id)/('backup-'+str(uuid.uuid4())+'.pending')
                    with closing(sqlite3.connect(temporary)) as saved:conn.backup(saved)
                    try:os.link(temporary,backup)
                    except FileExistsError:pass
                    finally:temporary.unlink()
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('CREATE TABLE IF NOT EXISTS edit_meta (key TEXT PRIMARY KEY,value INTEGER NOT NULL)')
            conn.execute('CREATE TABLE IF NOT EXISTS edit_history (seq INTEGER PRIMARY KEY,row_id INTEGER,col INTEGER,before TEXT,after TEXT,action TEXT,reference INTEGER,reason TEXT,at TEXT)')
            conn.execute('CREATE TABLE IF NOT EXISTS edit_stack (position INTEGER PRIMARY KEY,reference INTEGER NOT NULL)')
            conn.execute("INSERT OR IGNORE INTO edit_meta VALUES ('revision',0)")
            conn.execute("INSERT OR IGNORE INTO edit_meta VALUES ('cursor',0)")
            conn.commit();return conn
        except Exception:
            conn.close();raise
    def edit_state(self,id):
        with closing(self.edit_connection(id)) as conn:
            revision,cursor=(conn.execute('SELECT value FROM edit_meta WHERE key=?',(k,)).fetchone()[0] for k in ['revision','cursor'])
            total=conn.execute('SELECT count(*) FROM edit_stack').fetchone()[0]
            def preview(position):
                item=conn.execute('SELECT h.row_id,h.col,h.before,h.after FROM edit_stack s JOIN edit_history h ON h.seq=s.reference WHERE s.position=?',(position,)).fetchone()
                if not item:return None
                result=dict(zip(['row','column','before','after'],item))
                if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='large_batch_groups'").fetchone():
                    group=conn.execute('SELECT count FROM large_batch_groups WHERE reference=(SELECT reference FROM edit_stack WHERE position=?)',(position,)).fetchone()
                    if group:result['batchCells']=group[0]
                return result
            return {'nextUndo':preview(cursor),'nextRedo':preview(cursor+1),'revision':revision,'canUndo':cursor>0,'canRedo':cursor<total,'historyEntries':conn.execute('SELECT count(*) FROM edit_history').fetchone()[0], 'statistics':'Import-time profiles describe the original extraction; they are not recalculated after edits.'}
    def edit(self,id,revision,row=None,column=None,value=None,expected=None,reason='',action='edit'):
        if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValueError('A change rationale of 1–2000 characters is required.')
        if action not in ['edit','undo','redo']:raise ValueError('Unsupported edit action.')
        with self.lock,closing(self.edit_connection(id)) as conn:
            try:
                conn.execute('BEGIN IMMEDIATE')
                current,cursor=(conn.execute('SELECT value FROM edit_meta WHERE key=?',(k,)).fetchone()[0] for k in ['revision','cursor'])
                if type(revision)!=int or revision!=current:raise ValueError('Revision conflict: reload the page before editing.')
                reference=None
                if action=='edit':
                    if type(row)!=int or type(column)!=int or not 0<=column<len(self.status(id)['headers']):raise ValueError('Invalid row or column.')
                    if not isinstance(value,str) or len(value.encode('utf-8'))>1024*1024:raise ValueError('Value exceeds 1 MiB.')
                    record=conn.execute('SELECT data FROM rows WHERE id=?',(row,)).fetchone()
                    if record is None:raise ValueError('Record not found.')
                    values=json.loads(record[0]);before=values[column]
                    if before!=expected:raise ValueError('Value conflict: reload the page before editing.')
                    if before==value:raise ValueError('No value changed.')
                else:
                    position=cursor if action=='undo' else cursor+1
                    item=conn.execute('SELECT reference FROM edit_stack WHERE position=?',(position,)).fetchone()
                    if item is None:raise ValueError('Nothing to '+action+'.')
                    reference=item[0]
                    from large_repair import undo_group
                    if undo_group(conn,reference,action,reason):
                        cursor+=-1 if action=='undo' else 1
                        conn.execute("UPDATE edit_meta SET value=? WHERE key='cursor'",(cursor,))
                        conn.execute("UPDATE edit_meta SET value=? WHERE key='revision'",(current+1,))
                        conn.commit();return self.edit_state(id)
                    row,column,old,new=conn.execute('SELECT row_id,col,before,after FROM edit_history WHERE seq=?',(reference,)).fetchone()
                    values=json.loads(conn.execute('SELECT data FROM rows WHERE id=?',(row,)).fetchone()[0]);before=values[column];value=old if action=='undo' else new
                    if before!=(new if action=='undo' else old):raise ValueError('History value conflict; no change applied.')
                values[column]=value
                conn.execute('UPDATE rows SET data=? WHERE id=?',(json.dumps(values,ensure_ascii=False),row))
                event=conn.execute('INSERT INTO edit_history(row_id,col,before,after,action,reference,reason,at) VALUES (?,?,?,?,?,?,?,?)',(row,column,before,value,action,reference,reason.strip(),now())).lastrowid
                if action=='edit':
                    conn.execute('DELETE FROM edit_stack WHERE position>?',(cursor,));cursor+=1;conn.execute('INSERT INTO edit_stack VALUES (?,?)',(cursor,event))
                else:cursor+=-1 if action=='undo' else 1
                conn.execute("UPDATE edit_meta SET value=? WHERE key='cursor'",(cursor,))
                conn.execute("UPDATE edit_meta SET value=? WHERE key='revision'",(current+1,))
                conn.commit()
            except Exception:conn.rollback();raise
        return self.edit_state(id)
    def history(self,id):
        with closing(self.edit_connection(id)) as conn:
            conn.execute('BEGIN')
            for seq,row,col,before,after,action,reference,reason,at in conn.execute('SELECT * FROM edit_history ORDER BY seq'):
                yield (json.dumps({'sequence':seq,'sourceRecord':row,'column':col,'before':before,'after':after,'action':action,'reference':reference,'rationale':reason,'at':at},ensure_ascii=False)+'\n').encode('utf-8')
