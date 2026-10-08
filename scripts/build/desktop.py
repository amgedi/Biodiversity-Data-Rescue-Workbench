"""Build the Windows engine with existing readers and pinned local resources."""
from pathlib import Path
import subprocess, sys, ast, datetime
ROOT=Path(__file__).resolve().parents[2]
desktop=ROOT/'app/desktop/src-tauri'
def main():
    from PIL import Image
    import cryptography
    if cryptography.__version__!='50.0.2':raise RuntimeError('Install the pinned requirements-crypto.txt before building the encrypted portability engine.')
    icons=desktop/'icons';icons.mkdir(parents=True,exist_ok=True)
    with Image.open(ROOT/'web/branding/biodiversity-icon-master.png') as image:
        image.convert('RGBA').save(icons/'icon.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--onedir','--console','--name','workbench-engine','--distpath',str(ROOT/'artifacts/build/engine'),'--workpath',str(ROOT/'artifacts/build/pyinstaller'),'--specpath',str(ROOT/'artifacts/build')]
    for name in ('web','examples','vendor','vendor-xls','vendor-dwca'):
        command+=['--add-data',str(ROOT/name)+':'+name]
    for name in ('pdf_worker','xls_worker','doc_worker','ocr_worker','jsonschema','referencing','lxml.etree','cryptography.hazmat.primitives.ciphers','cryptography.hazmat.primitives.kdf.pbkdf2'):
        command+=['--hidden-import',name]
    # Vendored reader source is loaded from hash-checked data at runtime. Tell the
    # freezer about its standard-library imports without bundling optional cloud
    # or scientific packages merely because they exist on the development host.
    imports=set()
    for path in (ROOT/'vendor/pypdf').rglob('*.py'):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            names=[alias.name for alias in node.names] if isinstance(node,ast.Import) else [node.module] if isinstance(node,ast.ImportFrom) and not node.level else []
            imports.update(name for name in names if name and name.split('.')[0] in sys.stdlib_module_names)
    for name in sorted(imports):command+=['--hidden-import',name]
    command+=[str(ROOT/'desktop_service.py')]
    subprocess.run(command,cwd=ROOT,check=True)
    import shutil
    if (desktop/'engine').exists():
        history=ROOT/'artifacts/build/history';history.mkdir(parents=True,exist_ok=True)
        (desktop/'engine').rename(history/('engine-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')))
    shutil.copytree(ROOT/'artifacts/build/engine/workbench-engine',desktop/'engine',ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.pyo'))
    print('Engine staged; compile the Tauri shell next.')
if __name__=='__main__':main()
