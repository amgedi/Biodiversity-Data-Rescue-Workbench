import urllib.request,json,hashlib,concurrent.futures
from pathlib import Path
root=Path(__file__).resolve().parent.parent/'vendor/biodiversity';root.mkdir(parents=True,exist_ok=True)
records=[]
def fetch(url):return urllib.request.urlopen(url,timeout=30).read()
def group(repo,ref,names,label):
 commit=json.loads(fetch('https://api.github.com/repos/'+repo+'/commits/'+ref))['sha'];folder=root/label;folder.mkdir(exist_ok=True)
 def one(name):
  url='https://raw.githubusercontent.com/'+repo+'/'+commit+'/'+name;data=fetch(url);path=folder/Path(name).name;path.write_bytes(data);return {'path':str(path.relative_to(root)).replace('\\','/'),'url':url,'sha256':hashlib.sha256(data).hexdigest(),'commit':commit}
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:records.extend(pool.map(one,names))
 return commit
group('tdwg/camtrap-dp','1.0.2',['camtrap-dp-profile.json','deployments-table-schema.json','media-table-schema.json','observations-table-schema.json','LICENSE'],'camtrap-1.0.2')
xsd=json.loads(fetch('https://api.github.com/repos/NCEAS/eml/contents/xsd?ref=RELEASE_EML_2_2_0'));group('NCEAS/eml','RELEASE_EML_2_2_0',[x['path'] for x in xsd if x['name'].endswith('.xsd')]+['LICENSE'],'eml-2.2.0')
(root/'sources.json').write_text(json.dumps(records,indent=2),encoding='utf-8');print('Vendored',len(records),'resources with immutable revision and SHA-256')
