"""Explicit offline workspace copying; source is retained and every byte verified."""
import argparse, hashlib, json, os, shutil, sys, uuid, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from workspace_lock import WorkspaceLock

def copy_workspace(source,destination,commit=False):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if source==destination or source.is_relative_to(destination) or destination.is_relative_to(source):raise ValueError('Source and destination must be separate, non-overlapping directories.')
    if not source.is_dir():raise ValueError('Source workspace is missing.')
    if destination.exists():raise ValueError('Destination must not already exist. Stop both services before copying.')
    with WorkspaceLock(source):
        records=[]
        for directory,dirs,names in os.walk(source,followlinks=False):
            for name in dirs+names:
                path=Path(directory)/name
                if path.is_symlink() or getattr(path,'is_junction',lambda:False)():raise ValueError('Workspace links require separate review.')
            for name in names:
                path=Path(directory)/name
                if name=='.workspace-server.lock':continue
                with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
                records.append({'path':path.relative_to(source).as_posix(),'bytes':path.stat().st_size,'sha256':digest})
        if not commit:return {'files':len(records),'bytes':sum(item['bytes'] for item in records),'copyPerformed':False,'originalsRetained':True}
        destination.parent.mkdir(parents=True,exist_ok=True)
        backup=destination.parent/('pre-copy-'+uuid.uuid4().hex+'.zip')
        staging=destination.parent/(destination.name+'.pending-'+uuid.uuid4().hex)
        with zipfile.ZipFile(backup,'w',zipfile.ZIP_DEFLATED) as archive:
            for item in records:archive.write(source/item['path'],item['path'])
            archive.writestr('copy-manifest.json',json.dumps(records))
        with zipfile.ZipFile(backup) as archive:
            for item in records:
                if hashlib.sha256(archive.read(item['path'])).hexdigest()!=item['sha256']:raise ValueError('Backup verification failed.')
        staging.mkdir()
        try:
            for item in records:
                target=staging/item['path'];target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(source/item['path'],target)
                with target.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
                if target.stat().st_size!=item['bytes'] or digest!=item['sha256']:raise ValueError('Destination verification failed.')
            os.replace(staging,destination)
        except Exception:
            # Preserve an incomplete staging copy for explicit recovery; never delete source.
            raise
        return {'files':len(records),'copyPerformed':True,'originalsRetained':True,'backup':str(backup)}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('destination',type=Path);parser.add_argument('--copy',action='store_true');args=parser.parse_args()
    print(json.dumps(copy_workspace(args.source,args.destination,args.copy),indent=2))
