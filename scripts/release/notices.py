from pathlib import Path
import importlib.metadata,json,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
def collect(destination):
 destination.mkdir(parents=True,exist_ok=True);inventory=[]
 def retain(group,name,version,license_value,files):
  folder=destination/group/(name+'-'+version);folder.mkdir(parents=True,exist_ok=True);copied=[]
  for i,p in enumerate(files):
   if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo'):
    target=folder/(str(i)+'-'+p.name);shutil.copy2(p,target);copied.append(target.relative_to(destination).as_posix())
  inventory.append({'group':group,'name':name,'version':version,'license':license_value,'notices':copied})
 base=Path(sys.base_prefix)/'LICENSE.txt'
 if not base.is_file():raise RuntimeError('Python distribution license is missing')
 retain('python','CPython',sys.version.split()[0],'PSF', [base])
 for dist in importlib.metadata.distributions():
  files=[Path(dist.locate_file(f)) for f in (dist.files or []) if any(part.lower().startswith(('license','licence','copying','notice')) for part in f.parts)]
  retain('python',dist.metadata['Name'],dist.version,dist.metadata.get('License-Expression') or dist.metadata.get('License','See notices'),files)
 seen=set()
 for component in ['desktop','launcher']:
  result=subprocess.run(['cargo','metadata','--locked','--filter-platform','x86_64-pc-windows-msvc','--format-version','1'],cwd=ROOT/'app'/component/'src-tauri',capture_output=True,text=True,encoding='utf-8',check=True)
  metadata=json.loads(result.stdout);resolved={n['id'] for n in metadata['resolve']['nodes']}
  for package in metadata['packages']:
   if package['id'] not in resolved or package['id'] in seen or package['source'] is None:continue
   seen.add(package['id']);base=Path(package['manifest_path']).parent
   files=[p for p in base.iterdir() if p.is_file() and p.name.lower().startswith(('license','licence','copying','notice'))]
   if package.get('license_file'):files.append(base/package['license_file'])
   supplement=ROOT/'third-party/licenses'/(package['name']+'-'+package['version'])
   if supplement.is_dir():files.extend(p for p in supplement.iterdir() if p.is_file())
   if not files:raise RuntimeError('Dependency license notice missing: '+package['name'])
   retain('rust',package['name'],package['version'],package.get('license') or 'See notices',files)
 for name in ['react','react-dom','scheduler']:
  base=ROOT/'node_modules'/name;package=json.loads((base/'package.json').read_text())
  retain('javascript',name,package['version'],package.get('license'),[p for p in base.iterdir() if p.is_file() and p.name.lower().startswith(('license','notice'))])
 (destination/'INVENTORY.json').write_text(json.dumps({'scope':'Conservative build dependency and runtime notice inventory; bundled reader licenses also remain inside engine resources. This inventory can include build-only dependencies.','components':inventory},indent=2))
 return len(inventory)
