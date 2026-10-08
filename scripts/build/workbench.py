"""Single local build/launch backend. Never installs tools or changes research data."""
from pathlib import Path
import argparse, datetime, hashlib, importlib.util, json, os, shutil, subprocess, sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
CHECKPOINT = 'workstation-ui-v7'
STATE = ROOT / 'artifacts/build/current'

def source_files():
    files = list(ROOT.glob('*.py'))
    for name in ('web', 'scripts/build', 'scripts/release', 'scripts/launcher', 'vendor', 'vendor-xls', 'vendor-dwca', 'app/desktop/startup', 'app/desktop/src-tauri/src', 'app/desktop/src-tauri/capabilities', 'app/desktop/src-tauri/permissions', 'app/launcher/src', 'app/launcher/web','app/launcher/src-tauri/src','app/launcher/src-tauri/capabilities'):
        files += [p for p in (ROOT/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name != 'build-identity.json']
    for name in ('package.json','package-lock.json','requirements-crypto.txt','requirements-standards.txt','app/desktop/src-tauri/Cargo.toml','app/desktop/src-tauri/Cargo.lock','app/desktop/src-tauri/build.rs','app/desktop/src-tauri/tauri.conf.json','app/launcher/src-tauri/Cargo.toml','app/launcher/src-tauri/Cargo.lock','app/launcher/src-tauri/build.rs','app/launcher/src-tauri/tauri.conf.json'):
        files.append(ROOT/name)
    candidates=sorted(set(p for p in files if p.is_file()))
    if (ROOT/'.git').exists():
        result=subprocess.run(['git','ls-files','-z'],cwd=ROOT,capture_output=True,check=True)
        tracked=set(result.stdout.decode('utf-8').split('\0'))
        candidates=[p for p in candidates if p.relative_to(ROOT).as_posix() in tracked]
    return candidates

def identity():
    manifest = {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files()}
    digest = lambda items: hashlib.sha256(json.dumps(items, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'version':json.loads((ROOT/'package.json').read_text())['version'], 'checkpoint':CHECKPOINT,
            'sourceFingerprint':digest(manifest), 'frontendFingerprint':digest({n:h for n,h in manifest.items() if n.startswith('web/')}),
            'engineFingerprint':digest({n:h for n,h in manifest.items() if n.endswith('.py') and '/' not in n or n.startswith(('vendor/','vendor-xls/','vendor-dwca/'))}),
            'gitCommit':None, 'sourceFiles':manifest}

def status():
    now=identity(); path=STATE/'build-identity.json'
    built=json.loads(path.read_text()) if path.exists() else None
    exe=ROOT/'app/desktop/src-tauri/target/release/biodiversity-workbench.exe'
    current=bool(built and exe.exists() and built['sourceFingerprint']==now['sourceFingerprint'] and built.get('executableSHA256')==hashlib.sha256(exe.read_bytes()).hexdigest())
    tools={'Python':sys.executable,'Node':shutil.which('node'),'Cargo':shutil.which('cargo'),'Tauri CLI':str(ROOT/'node_modules/.bin/tauri.cmd') if (ROOT/'node_modules/.bin/tauri.cmd').exists() else None,
           'PyInstaller':bool(importlib.util.find_spec('PyInstaller')), 'Pillow':bool(importlib.util.find_spec('PIL')), 'cryptography':bool(importlib.util.find_spec('cryptography'))}
    return {'source':{k:v for k,v in now.items() if k!='sourceFiles'},'built':{k:v for k,v in built.items() if k!='sourceFiles'} if built else None,'current':current,'executable':str(exe),'prerequisites':tools}

def stage(message): print('STAGE '+message,flush=True)

def validate_release_acceptance(record, fingerprint):
    return (isinstance(record,dict) and record.get('sourceFingerprint')==fingerprint
            and all(record.get(key) is True for key in ('featureParityComplete','desktopAcceptance','launcherAccepted','helpTutorialParity'))
            and type(record.get('packagedVisualIterations')) is int and record['packagedVisualIterations']>=3)

def build(release=False):
    subprocess.run(['node',str(ROOT/'scripts/build/ui_v7.mjs')],cwd=ROOT,check=True)
    (ROOT/'web/styles.css').write_text((ROOT/'web/v7/design-system/workstation.css').read_text(encoding='utf-8')+'\n'+(ROOT/'web/v7/design-system/pre-release.css').read_text(encoding='utf-8'),encoding='utf-8')
    subprocess.run(['node',str(ROOT/'scripts/build/launcher_v2.mjs')],cwd=ROOT,check=True)
    if release:
        acceptance_path=ROOT/'artifacts/qa/ui-v7/release-acceptance.json'
        acceptance=json.loads(acceptance_path.read_text()) if acceptance_path.exists() else None
        if not validate_release_acceptance(acceptance, identity()['sourceFingerprint']):
            raise RuntimeError('V7 canonical publication withheld: this source requires completed feature parity, desktop/launcher/Help acceptance and three actual packaged visual iterations. Use build for an acceptance candidate; the last canonical distribution remains intact.')
    if True:
        stage('Checking frontend and scientific regressions')
        subprocess.run(['node','--test','--test-isolation=none',*[str(p) for p in sorted((ROOT/'tests').glob('*.test.mjs'))]],cwd=ROOT,check=True)
        subprocess.run([sys.executable,'-m','unittest','discover','-s','tests'],cwd=ROOT,check=True)
    STATE.mkdir(parents=True,exist_ok=True)
    lock=STATE/'build.lock'
    try: handle=lock.open('x')
    except FileExistsError: raise RuntimeError('Another build owns build.lock. If a previous build was forcibly stopped, inspect its PID before removing that lock.')
    try:
        handle.write(str(os.getpid()));handle.close()
        missing=[k for k,v in status()['prerequisites'].items() if not v]
        if missing: raise RuntimeError('Missing prerequisites: '+', '.join(missing)+'. Install them explicitly; the launcher does not install dependencies.')
        stamp=identity();stamp['builtAt']=datetime.datetime.now(datetime.timezone.utc).isoformat();stamp['buildId']=CHECKPOINT+'-'+stamp['sourceFingerprint'][:12]
        stage('Freezing scientific engine')
        subprocess.run([sys.executable,str(ROOT/'scripts/build/desktop.py')],cwd=ROOT,check=True)
        stamp_path=ROOT/'app/desktop/src-tauri/engine/_internal/web/build-identity.json'
        stamp_path.write_text(json.dumps({k:v for k,v in stamp.items() if k!='sourceFiles'},indent=2))
        stage('Compiling native desktop shell')
        env=os.environ.copy();env['WORKBENCH_BUILD_ID']=stamp['buildId'];env['WORKBENCH_SOURCE_FINGERPRINT']=stamp['sourceFingerprint']
        subprocess.run([str(ROOT/'node_modules/.bin/tauri.cmd'),'build'],cwd=ROOT/'app/desktop/src-tauri',env=env,check=True)
        exe=ROOT/'app/desktop/src-tauri/target/release/biodiversity-workbench.exe'
        stamp['executableSHA256']=hashlib.sha256(exe.read_bytes()).hexdigest()
        web=ROOT/'app/desktop/src-tauri/engine/_internal/web'
        for p in (ROOT/'web').rglob('*'):
            if p.is_file() and p.name!='build-identity.json' and p.read_bytes()!=(web/p.relative_to(ROOT/'web')).read_bytes(): raise RuntimeError('Frontend parity failed: '+str(p))
        if identity()['sourceFingerprint']!=stamp['sourceFingerprint']: raise RuntimeError('Source changed during build. This build will not be marked current.')
        (STATE/'build-identity.json').write_text(json.dumps(stamp,indent=2))
        stage('Verified source / frozen frontend parity')
        stage('Compiling current root launcher and dispatcher')
        subprocess.run(['cargo','build','--release','--bins'],cwd=ROOT/'app/launcher/src-tauri',check=True)
        from scripts.launcher.versions import promote
        promote(stamp)
        if release:
            env['WORKBENCH_RELEASE_OUTPUT']=str(ROOT/'release/staging'/stamp['buildId'])
            subprocess.run([sys.executable,str(ROOT/'scripts/release/package.py')],cwd=ROOT,env=env,check=True)
        return stamp
    finally:
        handle.close();lock.unlink(missing_ok=True)

def main():
    if os.environ.get('WORKBENCH_LAUNCHER_GATE')=='1' and sys.stdin.readline().strip()!='START': raise RuntimeError('Launcher cancelled before owned job initialization.')
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['status','build','release','web','development','regression']);parser.add_argument('--port',type=int,default=8768);args=parser.parse_args()
    if args.mode=='regression':
        subprocess.run(['node','--test','--test-isolation=none',*[str(p) for p in sorted((ROOT/'tests').glob('*.test.mjs'))]],cwd=ROOT,check=True)
        subprocess.run([sys.executable,'-m','unittest','discover','-s','tests'],cwd=ROOT,check=True)
        return
    if args.mode=='status': print(json.dumps(status()));return
    if args.mode in ('build','release'): build(args.mode=='release');return
    data=Path(os.environ['WORKBENCH_LAUNCHER_DATA']) if os.environ.get('WORKBENCH_LAUNCHER_DATA') else Path(os.environ.get('LOCALAPPDATA',str(ROOT/'artifacts')))/'Biodiversity Data Rescue Workbench'/('development-data' if args.mode=='development' else 'launcher-web-data')
    stage('Starting isolated '+args.mode+' workspace')
    subprocess.run([sys.executable,'-X','utf8',str(ROOT/'server.py'),'--port',str(args.port),'--data-dir',str(data)],cwd=ROOT,check=True)

if __name__=='__main__':
    try: main()
    except Exception as error: print('ERROR '+str(error),flush=True);sys.exit(1)
