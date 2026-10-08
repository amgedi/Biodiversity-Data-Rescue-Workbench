"""Explicit local V7 runtime history; package.json remains the product version source."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys,tempfile,datetime
ROOT=Path(__file__).resolve().parents[2]
STATE=ROOT/'versions/CURRENT.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read():
 if not STATE.exists():return {'activeBuildId':None,'previousBuildId':None,'versions':{}}
 return json.loads(STATE.read_text())
def atomic(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile(mode='w',encoding='utf8',dir=path.parent,delete=False,suffix='.pending') as f:
  json.dump(value,f,indent=2);f.flush();os.fsync(f.fileno());temporary=f.name
 os.replace(temporary,path)
def verify(state,bid):
 entry=state['versions'][bid];folder=(ROOT/entry['directory']).resolve();folder.relative_to((ROOT/'versions').resolve())
 identity=json.loads((folder/'build-identity.json').read_text())
 assert identity==entry['identity'] and identity['buildId']==bid,'Active identity differs'
 assert sha(folder/'Biodiversity Workbench.exe')==identity['executableSHA256'],'Desktop checksum mismatch'
 frozen=json.loads((folder/'engine/_internal/web/build-identity.json').read_text())
 for key in ['version','buildId','sourceFingerprint']:assert identity[key]==frozen[key],key+' differs'
 manifest=json.loads((folder/'SHA256.json').read_text())
 # Candidate inventories map relative paths directly to checksums.
 for name,expected in manifest.items():
  if isinstance(expected,dict):expected=expected.get('sha256') or expected.get('SHA256')
  path=(folder/name).resolve();path.relative_to(folder)
  assert sha(path)==expected,'Runtime file checksum mismatch: '+name
 return folder,identity
def running():
 command="Get-Process -ErrorAction SilentlyContinue | Where-Object {$_.ProcessName -in @('biodiversity-workbench','Biodiversity Workbench')} | Select-Object -ExpandProperty Id"
 return subprocess.check_output(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],creationflags=0x08000000).strip()
def activate(bid):
 state=read();verify(state,bid)
 if running():raise RuntimeError('Save and close Workbench before changing the active build. The launcher can stay open.')
 if bid!=state['activeBuildId']:
  state['previousBuildId']=state['activeBuildId'];state['activeBuildId']=bid;state['activatedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat();atomic(STATE,state)
 print('Activated '+bid)
def promote(stamp):
 """Tested build -> immutable runtime -> explicit active state -> stable root dispatchers -> native handshake.
 Failure restores the original active pointer. Root entry points never select by directory order.
 """
 before=read()
 if running():raise RuntimeError('Close Workbench before activating a development build')
 bid=stamp['buildId'];slot=ROOT/'versions'/bid;slot.parent.mkdir(parents=True,exist_ok=True)
 if slot.exists():raise RuntimeError('Version already exists; immutable runtime will not be overwritten')
 pending=ROOT/'versions'/('pending-'+bid)
 pending.mkdir()
 try:
  shutil.copy2(ROOT/'app/desktop/src-tauri/target/release/biodiversity-workbench.exe',pending/'Biodiversity Workbench.exe')
  shutil.copytree(ROOT/'app/desktop/src-tauri/engine',pending/'engine')
  atomic(pending/'build-identity.json',stamp)
  atomic(pending/'SHA256.json',{p.relative_to(pending).as_posix():sha(p) for p in pending.rglob('*') if p.is_file()})
  pending.rename(slot)
  next_state=json.loads(json.dumps(before));next_state['versions'][bid]={'directory':'versions/'+bid,'identity':stamp};next_state['previousBuildId']=before['activeBuildId'];next_state['activeBuildId']=bid
  verify(next_state,bid)
  atomic(ROOT/'artifacts/build/current/promotion-pending.json',{'buildId':bid,'verified':False})
  # Verify compiled launcher and root dispatcher before publishing the pointer.
  native=ROOT/'app/launcher/src-tauri/target/release'
  launcher=native/'workbench-launcher.exe';launcher_hash=sha(launcher);launcher_rel='app/launcher/runtime/launcher-'+launcher_hash[:16]+'.exe'
  installed=ROOT/launcher_rel;installed.parent.mkdir(parents=True,exist_ok=True)
  if not installed.exists():shutil.copy2(launcher,installed)
  next_state['launcher']={'path':launcher_rel,'sha256':launcher_hash,'version':stamp['version']}
  for source,dest in [('current-launcher.exe','Launch Workbench.exe'),('current-workbench.exe','Biodiversity Data Rescue Workbench.exe')]:
   if (ROOT/dest).is_file() and sha(native/source)==sha(ROOT/dest):continue
   temporary=ROOT/(dest+'.pending');shutil.copy2(native/source,temporary);os.replace(temporary,ROOT/dest)
  atomic(STATE,next_state)
  # Native launcher handles the selected runtime and verifies the observed engine identity.
  env=os.environ.copy();env['WORKBENCH_VERIFY_CURRENT']='1'
  result=subprocess.run([str(ROOT/'Launch Workbench.exe')],cwd=ROOT,env=env,timeout=90)
  if result.returncode:raise RuntimeError('Root launcher verification failed')
  record=json.loads((ROOT/'artifacts/qa/reconstruction/last-launch.json').read_text())
  assert record['observed']['buildId']==bid,'Launched build mismatch'
  atomic(ROOT/'artifacts/build/current/promotion-verified.json',{'buildId':bid,'rootLauncherSHA256':sha(ROOT/'Launch Workbench.exe'),'rootWorkbenchSHA256':sha(ROOT/'Biodiversity Data Rescue Workbench.exe'),'engineHandshake':True,'visibleAcceptance':False})
  print('STAGE Root launcher and Workbench identity verified: '+bid,flush=True)
 except BaseException:
  atomic(STATE,before)
  raise
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['status','verify','activate']);parser.add_argument('build_id',nargs='?');args=parser.parse_args()
 if args.action=='activate':activate(args.build_id)
 elif args.action=='verify':print(json.dumps(verify(read(),args.build_id or read()['activeBuildId'])[1],indent=2))
 else:print(json.dumps(read(),indent=2))
