"""Package a verified development/release runtime without private source/history."""
from pathlib import Path
import hashlib,json,os,shutil,zipfile
ROOT=Path(__file__).resolve().parents[2]
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def main():
 from scripts.launcher.versions import read,verify
 state=read();bid=state['activeBuildId'];runtime,identity=verify(state,bid);version=identity['version']
 output=Path(os.environ.get('WORKBENCH_RELEASE_OUTPUT',str(ROOT/'release/staging'/bid)))
 output=output.resolve();output.relative_to((ROOT/'release').resolve())
 if output.exists():raise RuntimeError('Package destination exists; preserve it and select a new directory.')
 output.mkdir(parents=True)
 portable=output/('Biodiversity-Data-Rescue-Workbench-'+version+'-Portable');portable.mkdir()
 for name in ['Launch Workbench.exe','Biodiversity Data Rescue Workbench.exe','LICENSE','THIRD_PARTY_NOTICES.md']:
  if not (ROOT/name).is_file():raise RuntimeError('Required package file missing: '+name)
  shutil.copy2(ROOT/name,portable/name)
 shutil.copytree(runtime,portable/'versions'/bid)
 launcher=state['launcher'];launcher_path=ROOT/launcher['path']
 if sha(launcher_path)!=launcher['sha256']:raise RuntimeError('Launcher checksum differs')
 target=portable/launcher['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(launcher_path,target)
 selected={'activeBuildId':bid,'previousBuildId':None,'versions':{bid:state['versions'][bid]},'launcher':launcher}
 (portable/'versions/CURRENT.json').write_text(json.dumps(selected,indent=2))
 for name in ['README.md','architecture.md','data-safety.md']:
  source=ROOT/'docs'/name
  if source.exists():target=portable/'docs'/name;target.parent.mkdir(exist_ok=True);shutil.copy2(source,target)
 (portable/'INSTALL.txt').write_text('Biodiversity Data Rescue Workbench '+version+'\n\nExtract the entire archive to a writable directory. Open Launch Workbench.exe. Keep all folders together. Windows x64 and WebView2 are required. Python and Node are not required.\n\nBinaries are unsigned. Verify SHA256SUMS.txt from a trusted source. Projects remain under the separate local application-data library. Saved projects are not independent backups.\n\nThis package contains one verified runtime. Local source installations can retain additional builds; this portable archive does not include private rollback history.\n\nNo automatic update installation is claimed. Use Check for updates to compare official GitHub releases, then obtain the complete newer package from the release page.\n')
 (portable/'SOURCE.txt').write_text('Original code: AGPL-3.0-only. Corresponding source and build instructions:\nhttps://github.com/amgedi/Biodiversity-Data-Rescue-Workbench\nBuild: '+bid+'\nVersion: '+version+'\nThird-party licenses remain with their source/resources.\n')
 checks={p.relative_to(portable).as_posix():sha(p) for p in portable.rglob('*') if p.is_file()}
 (portable/'SHA256.json').write_text(json.dumps(checks,indent=2))
 archive=output/(portable.name+'.zip')
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for p in portable.rglob('*'):
   if p.is_file():z.write(p,p.relative_to(portable.parent))
 with zipfile.ZipFile(archive) as z:assert z.testzip() is None
 manifest={'schemaVersion':1,'version':version,'tag':'v'+version,'buildId':bid,'sourceFingerprint':identity['sourceFingerprint'],'channel':'development' if '-' in version else 'stable','releaseUrl':'https://github.com/amgedi/Biodiversity-Data-Rescue-Workbench/releases/tag/v'+version,'assets':[{'name':archive.name,'sha256':sha(archive),'bytes':archive.stat().st_size}]}
 (output/'update-manifest.json').write_text(json.dumps(manifest,indent=2))
 assets=[archive,output/'update-manifest.json']
 (output/'SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in assets))
 for rel,digest in checks.items():assert sha(portable/rel)==digest
 print(json.dumps({'version':version,'buildId':bid,'output':str(output),'portableFilesVerified':len(checks),'zipReadback':True,'published':False}))
if __name__=='__main__':
 import sys
 sys.path.insert(0,str(ROOT));main()
