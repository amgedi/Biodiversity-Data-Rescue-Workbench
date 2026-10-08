"""Public build provenance without research paths, credentials or project content."""
from pathlib import Path
import json, sys

def describe():
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
    packaged=root/'web/build-identity.json'
    if getattr(sys,'frozen',False):
        if packaged.is_file(): return json.loads(packaged.read_text(encoding='utf-8'))
        return {'version':'0.7.0','buildId':'legacy-unidentified','sourceFingerprint':None,'builtAt':None,'gitCommit':None}
    from scripts.build.workbench import identity
    result=identity();result.pop('sourceFiles',None)
    result.update(buildId='source-'+result['sourceFingerprint'][:12],builtAt=None,mode='source')
    return result
