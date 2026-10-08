"""Offline message catalogs. Never apply translation to datasets or evidence records."""
import json,re
from functools import lru_cache
from pathlib import Path
ROOT=Path(__file__).resolve().parent/'web/translations'
LANGUAGES={'en','fr','es','pt-BR','de','nl','it','pl','tr','ar','zh-CN','ja','ko'}
@lru_cache(maxsize=13)
def catalog(locale='en'):
 if locale not in LANGUAGES:raise ValueError('Unsupported report language.')
 return json.loads((ROOT/(locale+'.json')).read_text(encoding='utf-8'))
@lru_cache(maxsize=1)
def patterns():
 out=[]
 for key,text in catalog().items():
  tokens=list(re.finditer(r'\{([A-Za-z][A-Za-z0-9_]*)\}',text))
  if not tokens or len(re.sub(r'\{[^}]+\}','',text))<12:continue
  pattern='';start=0;names=[]
  for token in tokens:
   pattern+=re.escape(text[start:token.start()])+r'([\s\S]*?)';names.append(token[1]);start=token.end()
  out.append((len(text),key,re.compile('^'+pattern+re.escape(text[start:])+'$'),names))
 return sorted(out,reverse=True)
def message(text,locale='en',args=None):
 if not isinstance(text,str):return text
 english=catalog();target=catalog(locale)
 key=next((k for k,v in english.items() if v==text),None)
 if key is not None:
  result=target.get(key,text)
  return re.sub(r'\{([A-Za-z][A-Za-z0-9_]*)\}',lambda m:str((args or {}).get(m[1],m[0])),result)
 for _,key,pattern,names in patterns():
  match=pattern.fullmatch(text)
  if match:
   values=dict(zip(names,match.groups()))
   return re.sub(r'\{([A-Za-z][A-Za-z0-9_]*)\}',lambda m:values[m[1]],target.get(key,english[key]))
 return text
def display_findings(findings,locale='en'):
 return [{**item,**{key:message(item[key],locale) for key in ['title','detail','description','severity','layer'] if isinstance(item.get(key),str)}} for item in findings]
