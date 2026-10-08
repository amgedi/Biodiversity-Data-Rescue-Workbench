from edit_sessions import registry,write_project_id,authorized_write
"""Loopback-only, zero-dependency application server."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import webbrowser
import socket
import secrets
from http.cookies import SimpleCookie
from rescue import inspect, export_project
from importers import ingest
from storage import Store
from exporters import export_v2
from standards import awareness
from biodiversity_validation import camtrap_tables,validate_uploaded,eml_validate
from upgrades import now,APP_VERSION,migration_preview,migrate_saved,snapshot,snapshots,open_snapshot,compare,recovery_status,save_draft,verify_package
from large_data import LargeStore
from exporters import public_tables
from management import describe,action as project_action,deletion_preview,permanently_delete,trash_preview,empty_trash
from rescue import source_bytes
LARGE=None

ROOT = Path(__file__).resolve().parent
STATIC = {'/': ('web/index.html', 'text/html; charset=utf-8'), '/app.mjs': ('web/app.mjs', 'text/javascript; charset=utf-8'), '/model.mjs': ('web/model.mjs', 'text/javascript; charset=utf-8'), '/styles.css': ('web/styles.css', 'text/css; charset=utf-8'), '/sample.csv': ('examples/woodland-survey.csv', 'text/csv; charset=utf-8')}
STATIC.update({'/coordinate-pair.mjs':('web/coordinate-pair.mjs','text/javascript; charset=utf-8')})
STATIC.update({'/taxonomy-review.mjs':('web/taxonomy-review.mjs','text/javascript; charset=utf-8')})
STATIC.update({'/date-calendar-v2.mjs':('web/date-calendar-v2.mjs','text/javascript; charset=utf-8')})
STATIC['/date-time-review.mjs']=('web/date-time-review.mjs','text/javascript; charset=utf-8')
STATIC['/ocr-review.mjs']=('web/ocr-review.mjs','text/javascript; charset=utf-8')
STATIC['/dwca-export.mjs']=('web/dwca-export.mjs','text/javascript; charset=utf-8')
STATIC.update({ '/key-comparison-core.mjs': ('web/key-comparison-core.mjs','text/javascript; charset=utf-8'), '/key-comparison-ui.mjs': ('web/key-comparison-ui.mjs','text/javascript; charset=utf-8')})
STATIC.update({'/app2.mjs':('web/app2.mjs','text/javascript; charset=utf-8'),'/project.mjs':('web/project.mjs','text/javascript; charset=utf-8'),'/upgrade.css':('web/upgrade.css','text/css; charset=utf-8'),'/demo.json':('examples/relational-demo.biorescue.json','application/json'),'/legacy-app.mjs':('web/legacy-app.mjs','text/javascript; charset=utf-8'),'/legacy':('web/legacy.html','text/html; charset=utf-8')})
for name in ['workspace-core.mjs','workspace-copy.mjs','context-inspector.mjs','advanced-workspace.css']:STATIC['/'+name]=('web/'+name,'text/css' if name.endswith('.css') else 'text/javascript')
STATIC['/tutorial-registry.mjs']=('web/tutorial-registry.mjs','text/javascript; charset=utf-8')
STATIC['/practice-catalog.mjs']=('web/practice-catalog.mjs','text/javascript; charset=utf-8')
for practice in ('amphibian','museum','camera'): STATIC['/practice-'+practice+'.json']=('examples/practice/'+practice+'.biorescue.json','application/json')
STATIC['/large-encrypted-backup.mjs']=('web/large-encrypted-backup.mjs','text/javascript; charset=utf-8')
STORE = Store(ROOT/'local-data')
LARGE = LargeStore(ROOT/'local-data'/'large')
for name,mime in [('dwc-preparation.mjs','text/javascript'),('window-recovery.mjs','text/javascript'),('edit-sessions.mjs','text/javascript'),('tour.mjs','text/javascript'),('refinement.css','text/css'),('brand-mark-192-v05.png','image/png'),('brand-mark-512-v05.png','image/png'),('manifest-v05.webmanifest','application/manifest+json'),('management.mjs','text/javascript'),('combobox.mjs','text/javascript'),('onboarding.mjs','text/javascript'),('settings-ui.mjs','text/javascript'),('i18n.mjs','text/javascript'),('commands.mjs','text/javascript'),('standards-center.mjs','text/javascript'),('locales.mjs','text/javascript'),('v05.css','text/css'),('drafts.mjs','text/javascript'),('components.mjs','text/javascript'),('advanced.mjs','text/javascript'),('encryption.mjs','text/javascript'),('shell.mjs','text/javascript'),('v03.css','text/css'),('theme.css','text/css'),('preferences.mjs','text/javascript'),('uploads.mjs','text/javascript'),('legacy-shell.mjs','text/javascript'),('sw.js','text/javascript'),('manifest.webmanifest','application/manifest+json'),('icon.svg','image/svg+xml'),('icon-192.png','image/png'),('icon-512.png','image/png')]:STATIC['/'+name]=('web/'+name,mime)
for name in ['document-evidence.mjs','large-restore.mjs','link-drafts.mjs','large-links.mjs','large-metadata.mjs','analysis-providers.mjs','mechanical-batch.mjs','note-targets.mjs','resume-context.mjs','comparison.mjs','templates.mjs','evidence-discovery.mjs','translation-ui.mjs','translation-core.mjs','source-integrity.mjs','import-discovery.mjs','settings-v06.mjs','workspace-profile.mjs','smart-analysis.mjs','guided-workspace.mjs','v06.css']:STATIC['/'+name]=('web/'+name,'text/css' if name.endswith('.css') else 'text/javascript')
for name in ['studio.css','studio.mjs','studio-copy.mjs','studio-themes.mjs','studio-icons.mjs','studio-settings.mjs','rescue-assistant.mjs','knowledge.mjs','desktop-client-state.mjs','glossary.mjs','help-workflows.mjs','desktop-health.mjs','experience-copy.mjs','workflow-experience.mjs','workflow-experience.css']:STATIC['/'+name]=('web/'+name,'text/css' if name.endswith('.css') else 'text/javascript')
for name in ['biodiversity-icon-32.png','biodiversity-icon-192.png','biodiversity-icon-512.png','branding/biodiversity-full-logo.png','branding/biodiversity-icon-master.png']:STATIC['/'+name]=('web/'+name,'image/png')
STATIC['/workbench.css']=('web/workbench.css','text/css; charset=utf-8')
STATIC['/build-identity.json']=('web/build-identity.json','application/json')
STATIC['/build-identity.mjs']=('web/build-identity.mjs','text/javascript')
STATIC['/biodiversity-mark.svg']=('web/biodiversity-mark.svg','image/svg+xml')
STATIC['/import-screening.mjs']=('web/import-screening.mjs','text/javascript')
STATIC['/nightmare.json']=('examples/nightmare.biorescue.json','application/json')


for name in ['first-run.mjs','table-workbench.mjs','structural-copy.mjs','workstation.mjs','workstation-copy.mjs','help-center.mjs','desktop-bridge.mjs','workstation.css']:STATIC['/'+name]=('web/'+name,'text/css' if name.endswith('.css') else 'text/javascript')

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Bootstrap URLs contain credentials. Desktop diagnostics never record them.
        if not getattr(self.server, 'desktop', False):super().log_message(format, *args)

    def allowed(self):
        host = self.headers.get('Host', '')
        valid = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
        origin_ok = host in valid and (not self.headers.get('Origin') or self.headers['Origin'] in {f'http://{h}' for h in valid})
        if not origin_ok:return False
        token = getattr(self.server, 'auth_token', None)
        if not token:return True
        cookie = SimpleCookie()
        try:cookie.load(self.headers.get('Cookie',''))
        except Exception:return False
        supplied = self.headers.get('X-Workbench-Token') or (cookie['workbench_session'].value if 'workbench_session' in cookie else '')
        return secrets.compare_digest(supplied,token)

    def reply(self, status, body, content_type='application/json; charset=utf-8'):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header('Referrer-Policy', 'no-referrer')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        token=getattr(self.server,'auth_token',None)
        if token and self.path.startswith('/desktop/'):
            host=self.headers.get('Host','')
            if self.headers.get('Origin') or host!=f'127.0.0.1:{self.server.server_port}' or not secrets.compare_digest(self.path[len('/desktop/'):],token):
                return self.reply(403,b'{"error":"Unauthorized desktop session."}')
            self.send_response(303)
            self.send_header('Set-Cookie',f'workbench_session={token}; HttpOnly; SameSite=Strict; Path=/')
            self.send_header('Location','/')
            self.send_header('Cache-Control','no-store')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Length','0');self.end_headers();return
        if not self.allowed():
            return self.reply(403, b'{"error":"Only local application requests are allowed."}')
        parsed = urlsplit(self.path)
        try:
            store = getattr(self.server, 'store', STORE)
            if parsed.path == '/api/build-identity':
                from build_identity import describe as build_identity
                return self.reply(200,json.dumps(build_identity()).encode())
            if parsed.path == '/api/ocr-capability':
                from ocr_candidates import capability
                return self.reply(200,json.dumps(capability()).encode())
            if parsed.path == '/api/project-hub':return self.reply(200,json.dumps(describe(store),ensure_ascii=False).encode())
            if parsed.path == '/api/trash-preview':return self.reply(200,json.dumps(trash_preview(store),ensure_ascii=False).encode())
            if parsed.path == '/api/delete-preview':return self.reply(200,json.dumps(deletion_preview(store,parse_qs(parsed.query).get('id',[''])[0]),ensure_ascii=False).encode())
            if parsed.path == '/api/dwc-preparation-options':
                from dwc_preparation import choices
                return self.reply(200,json.dumps(choices(),ensure_ascii=False).encode())
            if parsed.path == '/api/workspace':return self.reply(200,json.dumps({'isolated':getattr(self.server,'isolated',False),'desktop':getattr(self.server,'desktop',False),'applicationVersion':APP_VERSION,'projectSchemaVersion':3,'dataLocation':'application-data' if getattr(self.server,'desktop',False) else 'explicit workspace' if getattr(self.server,'isolated',False) else 'legacy source workspace'}).encode())
            if parsed.path == '/api/standards-center':
                from dwc_dp import capability
                from standards import PROFILES
                from importlib.util import find_spec
                validators={'jsonschema':find_spec('jsonschema') is not None,'referencing':find_spec('referencing') is not None,'lxml':find_spec('lxml') is not None}
                return self.reply(200,json.dumps({'profiles':PROFILES,'dwcDP':capability(),'validators':validators}).encode())
            if parsed.path == '/api/recovery':return self.reply(200,json.dumps(recovery_status(store,parse_qs(parsed.query).get('id',[''])[0])).encode())
            if parsed.path == '/api/snapshots':return self.reply(200,json.dumps(snapshots(store,parse_qs(parsed.query).get('id',[''])[0])).encode())
            large=getattr(self.server,'large',LARGE);q=parse_qs(parsed.query);lid=q.get('id',[''])[0]
            if parsed.path == '/api/large':return self.reply(200,json.dumps(large.list()).encode())
            if parsed.path == '/api/large-restore-inventory':return self.reply(200,json.dumps(large.interrupted_restores()).encode())
            if parsed.path == '/api/large-status':return self.reply(200,json.dumps(large.status(lid)).encode())
            if parsed.path == '/api/large-page':return self.reply(200,json.dumps(large.page(lid,int(q.get('offset',['0'])[0]),q.get('q',[''])[0],int(q.get('limit',['50'])[0])),ensure_ascii=False).encode())
            if parsed.path == '/api/large-metadata':
                from large_preservation import metadata
                return self.reply(200,json.dumps(metadata(large,lid),ensure_ascii=False).encode())
            if parsed.path == '/api/large-package':
                from large_preservation import package
                with package(large,lid) as archive:
                    archive.seek(0,2);size=archive.tell();archive.seek(0)
                    self.send_response(200);self.send_header('Content-Type','application/zip');self.send_header('Content-Length',str(size));self.send_header('Content-Disposition','attachment; filename=investigation-preservation.zip');self.send_header('Cache-Control','no-store');self.end_headers()
                    while block:=archive.read(65536):self.wfile.write(block)
                return
            if parsed.path == '/api/large-link-download':
                from temporary_exports import registry as export_registry
                item=export_registry(self.server).take(q.get('token',[''])[0])
                with item['file'] as archive:
                    self.send_response(200);self.send_header('Content-Type','application/zip');self.send_header('Content-Length',str(item['bytes']));self.send_header('Content-Disposition','attachment; filename=literal-relationship-preservation.zip');self.send_header('Cache-Control','no-store');self.end_headers()
                    while block:=archive.read(65536):self.wfile.write(block)
                return
            if parsed.path == '/api/large-edit-state':return self.reply(200,json.dumps(large.edit_state(lid)).encode())
            if parsed.path in ['/api/large-export','/api/large-original','/api/large-history']:
                large.status(lid)
                if parsed.path.endswith('export'):chunks=large.export(lid)
                elif parsed.path.endswith('history'):chunks=large.history(lid)
                else:
                    def original_chunks():
                        with (large.folder(lid)/'original.bin').open('rb') as f:
                            while block:=f.read(65536):yield block
                    chunks=original_chunks()
                iterator=iter(chunks);first=next(iterator,b'')
                self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('Content-Disposition','attachment; filename=investigation.csv' if parsed.path.endswith('export') else 'attachment; filename=original.bin');self.send_header('Cache-Control','no-store');self.send_header('Connection','close');self.end_headers();self.wfile.write(first)
                for block in iterator:self.wfile.write(block)
                self.close_connection=True;return
            if parsed.path == '/api/source-integrity':
                pid=parse_qs(parsed.query).get('id',[''])[0]
                return self.reply(200,json.dumps(store.verify(store.get(pid)),ensure_ascii=False).encode())
            if parsed.path == '/api/workspace-state':
                from workspace_state import read
                return self.reply(200,json.dumps(read(store,parse_qs(parsed.query).get('id',[''])[0]),ensure_ascii=False).encode())
            if parsed.path == '/api/projects':
                return self.reply(200, json.dumps(store.list()).encode())
            if parsed.path == '/api/project':
                query=parse_qs(parsed.query)
                return self.reply(200,json.dumps(store.get(query.get('id',[''])[0],query.get('previous',['0'])[0]=='1'),ensure_ascii=False).encode())
        except (ValueError,KeyError,OSError) as exc:
            return self.reply(400,json.dumps({'error':str(exc)}).encode())
        route = STATIC.get(parsed.path)
        if not route:
            return self.reply(404, b'{"error":"Not found"}')
        self.reply(200, (ROOT / route[0]).read_bytes(), route[1])

    def do_POST(self):
        if not self.allowed() or self.headers.get('Content-Type') != 'application/json':
            return self.reply(403, b'{"error":"Only local JSON requests are allowed."}')
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 150 * 1024 * 1024:
                raise ValueError('Request exceeds 150 MiB; reduce the project history or dataset size.')
            payload = json.loads(self.rfile.read(length))
            store = getattr(self.server, 'store', STORE)
            if self.path == '/api/edit-session':
                pid=payload['projectId']
                if pid.startswith('large:'):getattr(self.server,'large',LARGE).folder(pid[6:])
                else:store.path(pid)
                sessions=registry(self.server)
                action=payload.get('action','claim');session=payload.get('session');token=payload.get('token')
                if action in ['claim','takeover']:
                    from management import record
                    if not pid.startswith('large:') and record(store,pid)['state']!='active':raise ValueError('Restore the project before editing.')
                    result=sessions.claim(pid,session,action=='takeover',payload.get('generation'))
                elif action=='renew':result=sessions.renew(pid,session,token)
                elif action=='release':result=sessions.release(pid,session,token)
                else:raise ValueError('Invalid editing-session action.')
                return self.reply(200,json.dumps(result).encode())
            pid=write_project_id(self.path,payload)
            with authorized_write(self.server,pid,self.headers.get('X-Workspace-Session'),self.headers.get('X-Workspace-Token')):
                if self.path == '/api/workspace-state':
                    from workspace_state import save
                    return self.reply(200,json.dumps(save(store,payload),ensure_ascii=False).encode())
                if self.path == '/api/empty-trash':
                    from storage import LOCK
                    with LOCK:
                        for item in payload.get('projects',[]):registry(self.server).check(item['id'])
                        return self.reply(200,json.dumps(empty_trash(store,payload),ensure_ascii=False).encode())
                if self.path == '/api/project-action':return self.reply(200,json.dumps(project_action(store,payload),ensure_ascii=False).encode())
                if self.path == '/api/project-delete':return self.reply(200,json.dumps(permanently_delete(store,payload),ensure_ascii=False).encode())
                large=getattr(self.server,'large',LARGE)
                if self.path == '/api/ocr-preview':
                    from ocr_candidates import preview
                    project=store.get(payload['projectId']);source=next((r for r in project['resources'] if r['id']==payload.get('sourceId')),None)
                    if source is None:raise ValueError('OCR_SOURCE_UNAVAILABLE')
                    return self.reply(200,json.dumps(preview(source,payload.get('optIn')),ensure_ascii=False).encode())
                if self.path in ['/api/dwc-prepare','/api/dwc-export']:
                    from dwc_preparation import prepare,export as export_dwc
                    if self.path=='/api/dwc-export':return self.reply(200,export_dwc(payload),'application/zip')
                    descriptor,report,_=prepare(payload)
                    return self.reply(200,json.dumps({'descriptor':descriptor,'report':report},ensure_ascii=False).encode())
                if self.path == '/api/validate-standard':
                    report=camtrap_tables(payload['project']['tables']) if 'project' in payload else validate_uploaded(source_bytes(payload['source']),payload['source']['name'],payload.get('schemaProvider'))
                    return self.reply(200,json.dumps(report,ensure_ascii=False).encode())
                if self.path == '/api/migration-preview':return self.reply(200,json.dumps(migration_preview(payload)).encode())
                if self.path == '/api/migrate':return self.reply(200,json.dumps(migrate_saved(store,payload),ensure_ascii=False).encode())
                if self.path == '/api/snapshot':return self.reply(200,json.dumps(snapshot(store,payload['project'],payload['name']),ensure_ascii=False).encode())
                if self.path == '/api/snapshot-compare':return self.reply(200,json.dumps(compare(open_snapshot(store,payload['project']['id'],payload['snapshotId']),payload['project'])).encode())
                if self.path == '/api/draft':return self.reply(200,json.dumps(save_draft(store,payload)).encode())
                if self.path == '/api/verify-package':return self.reply(200,json.dumps(verify_package(source_bytes(payload['source']))).encode())
                if self.path == '/api/public-preview':
                    tables=public_tables(payload['project'],payload['policy']);return self.reply(200,json.dumps({'policy':payload['policy'],'includedFiles':['working/*.csv','schemas/*.json','datapackage.json','public-policy.json','checksums.sha256','README.txt'],'omitted':['originals','private metadata','evidence','audit','backup','reports'],'warning':'Preview contains ALL remaining values. Review free text and identifiers; no full anonymity guarantee.','tables':[{'name':t['name'],'headers':t['headers'],'rows':t['rows'],'fields':[{'name':h,'description':c.get('description',''),'unit':c.get('unit',''),'status':c.get('status')} for h,c in zip(t['headers'],t['columns'])]} for t in tables]},ensure_ascii=False).encode())
                if self.path == '/api/large-metadata':
                    from large_preservation import save_metadata
                    return self.reply(200,json.dumps(save_metadata(large,payload),ensure_ascii=False).encode())
                if self.path == '/api/large-edit':return self.reply(200,json.dumps(large.edit(payload['id'],payload['revision'],payload.get('row'),payload.get('column'),payload.get('value'),payload.get('expected'),payload.get('reason',''),payload.get('action','edit'))).encode())
                if self.path == '/api/snapshot-restore':
                    import uuid
                    restored=open_snapshot(store,payload['projectId'],payload['snapshotId']);restored['id']=str(uuid.uuid4());restored['revision']=0
                    restored['audit'].append({'id':str(uuid.uuid4()),'at':now(),'action':'restore snapshot as separate project','reason':'Checkpoint restored with verified original bytes; current project retained.','sourceProjectId':payload['projectId'],'snapshotId':payload['snapshotId'],'applicationVersion':APP_VERSION})
                    return self.reply(200,json.dumps(store.save(restored),ensure_ascii=False).encode())
                if self.path == '/api/large-batch-preview':
                    from large_repair import preview
                    return self.reply(200,json.dumps(preview(large,payload),ensure_ascii=False).encode())
                if self.path == '/api/large-batch-trim':
                    from large_repair import apply
                    return self.reply(200,json.dumps(apply(large,payload),ensure_ascii=False).encode())
                if self.path == '/api/large-link-preview':
                    from large_relationships import inspect as inspect_links
                    return self.reply(200,json.dumps(inspect_links(large,payload),ensure_ascii=False).encode())
                if self.path == '/api/large-link-save':
                    from large_relationships import save as save_link
                    return self.reply(200,json.dumps(save_link(large,payload),ensure_ascii=False).encode())
                if self.path == '/api/large-link-export':
                    from large_relationships import package as link_package
                    from temporary_exports import registry as export_registry
                    return self.reply(200,json.dumps(export_registry(self.server).create(lambda:link_package(large,payload))).encode())
                if self.path == '/api/dwca-preview':
                    from dwca_export import preview
                    return self.reply(200,json.dumps(preview(payload['project'],payload['selection']),ensure_ascii=False).encode())
                if self.path == '/api/dwca-export':
                    from dwca_export import package
                    from temporary_exports import registry as export_registry
                    return self.reply(200,json.dumps(export_registry(self.server).create(lambda:package(payload['project'],payload['selection'],payload['review']))).encode())
                if self.path == '/api/large-encrypted-export':
                    from large_encryption import export_package
                    from temporary_exports import registry as export_registry
                    return self.reply(200,json.dumps(export_registry(self.server).create(lambda:export_package(large,payload))).encode())
                if self.path.startswith('/api/large-restore-'):
                    from restore_uploads import registry as restore_registry
                    uploads=restore_registry(self.server)
                    if self.path=='/api/large-restore-create':result=uploads.create(payload['size'])
                    elif self.path=='/api/large-restore-chunk':result=uploads.chunk(payload['token'],payload['offset'],payload['data'])
                    elif self.path=='/api/large-restore-preview':result=uploads.preview(payload['token'],payload.get('password'))
                    elif self.path=='/api/large-restore-publish':result=uploads.publish(payload['token'],large,payload.get('digest'),payload.get('reviewer'),payload.get('reason'))
                    elif self.path=='/api/large-restore-cancel':result=uploads.cancel(payload['token'])
                    else:raise ValueError('LARGE_RESTORE_INVALID')
                    return self.reply(200,json.dumps(result,ensure_ascii=False).encode())
                if self.path == '/api/large-create':return self.reply(200,json.dumps(large.create(payload['name'],payload['size'],payload.get('encoding','utf-8-sig'),payload.get('delimiter',','))).encode())
                if self.path == '/api/large-chunk':return self.reply(200,json.dumps(large.chunk(payload['id'],payload['offset'],payload['data'])).encode())
                if self.path == '/api/large-start':return self.reply(200,json.dumps(large.start(payload['id'])).encode())
                if self.path == '/api/large-cancel':return self.reply(200,json.dumps(large.cancel(payload['id'])).encode())
                if self.path == '/api/inspect':
                    self.reply(200, json.dumps(inspect(payload), ensure_ascii=False).encode())
                elif self.path == '/api/export':
                    self.reply(200, export_v2(payload) if payload.get('version')==2 or payload.get('project',{}).get('version')==2 else export_project(payload), 'application/zip')
                elif self.path == '/api/ingest':
                    self.reply(200,json.dumps(ingest(payload),ensure_ascii=False).encode())
                elif self.path == '/api/save':
                    self.reply(200,json.dumps(store.save(payload),ensure_ascii=False).encode())
                elif self.path == '/api/verify':
                    self.reply(200,json.dumps(store.verify(payload),ensure_ascii=False).encode())
                elif self.path == '/api/standards':
                    self.reply(200,json.dumps(awareness(payload)).encode())
                else:
                    self.reply(404, b'{"error":"Not found"}')
        except (ValueError, TypeError, KeyError, OverflowError, OSError) as exc:
            self.reply(400, json.dumps({'error': str(exc)}).encode())


class LocalServer(ThreadingHTTPServer):
    allow_reuse_address=False
    # Cold browser module graphs open a burst of loopback connections on Windows.
    request_queue_size=128
    def server_bind(self):
        if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        super().server_bind()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--open', action='store_true')
    parser.add_argument('--data-dir',type=Path,help='Explicit isolated workspace for testing; never inferred from a project name.')
    args = parser.parse_args()
    url = f'http://127.0.0.1:{args.port}'
    from workspace_lock import WorkspaceLock
    try:workspace_lock=WorkspaceLock(args.data_dir.resolve() if args.data_dir else STORE.root)
    except ValueError as exc:
        print(str(exc),flush=True);raise SystemExit(1)
    try:server = LocalServer(('127.0.0.1', args.port), Handler)
    except OSError:
        print(f'Port {args.port} is already in use. Stop the previous Workbench server before upgrading. No second server was started.',flush=True)
        raise SystemExit(1)
    if args.data_dir:
        server.store=Store(args.data_dir.resolve());server.large=LargeStore(args.data_dir.resolve()/'large');server.isolated=True
    from purge_transactions import recover as recover_purges
    recovered_purges=recover_purges(getattr(server,'store',STORE))
    if recovered_purges:print('Reviewed purge recovery: '+', '.join(item['result'] for item in recovered_purges),flush=True)
    print(f'Biodiversity Workbench running at {url}\nAll processing stays on this computer. Press Ctrl+C to stop.', flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
    finally:
        workspace_lock.close()


