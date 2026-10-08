"""Desktop engine lifecycle; stdin bootstrap keeps launch credentials off command lines."""
import json, os, secrets, sys, threading
from pathlib import Path

def run():
    if len(sys.argv)>2 and sys.argv[1]=='--worker':
        import runpy
        worker=sys.argv[2]
        if worker not in {'pdf_worker','xls_worker','doc_worker','ocr_worker'}:raise SystemExit(2)
        sys.argv=[worker]+sys.argv[3:]
        runpy.run_module(worker,run_name='__main__');return
    import server
    from build_identity import describe
    print("Build identity: "+json.dumps(describe()),file=sys.stderr,flush=True)
    from storage import Store
    from large_data import LargeStore
    from workspace_lock import WorkspaceLock
    from purge_transactions import recover
    config=json.loads(sys.stdin.readline())
    root=Path(config['dataDir']).resolve()
    token=secrets.token_urlsafe(32)
    with WorkspaceLock(root):
        service=server.LocalServer(('127.0.0.1',0),server.Handler)
        service.store=Store(root);service.large=LargeStore(root/'large')
        service.auth_token=token;service.desktop=True;service.isolated=bool(config.get('isolated'))
        recover(service.store)
        print(json.dumps({'port':service.server_port,'token':token}),flush=True)
        # Parent closes this pipe on normal exit or crash. Shutdown waits for writes.
        def parent_watch():
            for _ in sys.stdin:pass
            service.shutdown()
        threading.Thread(target=parent_watch,daemon=True).start()
        try:service.serve_forever()
        finally:service.server_close()

if __name__=='__main__':run()
