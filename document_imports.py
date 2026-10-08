"""Passive, bounded supporting-document and XML inspection. No active content."""
import gzip,io,json,re,tarfile
from collections import Counter
from pathlib import PurePosixPath,Path
from xml.etree import ElementTree as ET
from rescue import source_bytes
from upgrades import safe_archive
MAX_XML_NODES=100000

def xml_tree(data):
 if data.startswith((b'\xff\xfe\x00\x00',b'\x00\x00\xfe\xff')):raise ValueError('DOCUMENT_XML_ENCODING')
 if data.startswith((b'\xff\xfe',b'\xfe\xff')):decoded=data.decode('utf-16')
 else:decoded=data.decode('utf-8-sig')
 if '\x00' in decoded:raise ValueError('DOCUMENT_XML_ENCODING')
 if '<!DOCTYPE' in decoded.upper() or '<!ENTITY' in decoded.upper():raise ValueError('DOCUMENT_XML_DECLARATION')
 depth=count=0;root=None
 for event,node in ET.iterparse(io.BytesIO(data),events=['start','end']):
  if event=='start':
   depth+=1;count+=1
   if depth>64 or count>MAX_XML_NODES or len(node.attrib)>250:raise ValueError('DOCUMENT_XML_LIMIT')
   if root is None:root=node
  else:
   if len(node.text or '')>1024*1024 or len(node.tail or '')>1024*1024:raise ValueError('DOCUMENT_XML_LIMIT')
   depth-=1
 if root is None:raise ValueError('DOCUMENT_XML_EMPTY')
 return root,count

def xml(source,options):
 root,node_count=xml_tree(source_bytes(source));paths={};previews=[]
 def visit(node,path):
  current=path+[node.tag];identity=json.dumps(current,ensure_ascii=False)
  if identity not in paths:
   if len(paths)>=200:raise ValueError('DOCUMENT_XML_PATH_LIMIT')
   paths[identity]={'path':current,'records':[]}
  paths[identity]['records'].append(node)
  if not len(node) and (node.text or '').strip() and len(previews)<50:previews.append({'location':current,'text':(node.text or '')[:1000],'truncated':len(node.text or '')>1000})
  for child in node:visit(child,current)
 visit(root,[])
 candidates=[{'path':item['path'],'records':len(item['records']),'attributes':sorted(set(key for node in item['records'] for key in node.attrib))[:250]} for item in paths.values()]
 archaeology={'xml':{'root':root.tag,'nodes':node_count,'recordPaths':candidates,'selection':'No record path is assumed. Select an exact expanded-name path to request a flat literal table.'},'documentPreview':{'kind':'xml','blocks':previews,'bounded':True,'notes':['Text excerpts are structural evidence only. Namespaces remain expanded names; no scientific meanings are inferred. No record path was selected automatically.']}}
 selected=options.get('xmlRecordPath')
 if selected is None:return [],archaeology
 if not isinstance(selected,list) or not selected or any(not isinstance(tag,str) for tag in selected) or json.dumps(selected,ensure_ascii=False) not in paths:raise ValueError('DOCUMENT_XML_PATH')
 records=paths[json.dumps(selected,ensure_ascii=False)]['records'];headers=[];dictionaries=[]
 if len(records)>100000:raise ValueError('DOCUMENT_XML_LIMIT')
 for node in records:
  if len(node) and (node.text or '').strip():raise ValueError('DOCUMENT_XML_MIXED')
  values={'@'+key:value for key,value in node.attrib.items()};seen=set()
  for child in node:
   if len(child) or child.attrib or (child.tail or '').strip():raise ValueError('DOCUMENT_XML_COMPLEX')
   if child.tag in seen:raise ValueError('DOCUMENT_XML_REPEATED')
   seen.add(child.tag);values[child.tag]=child.text or ''
  if not len(node):values['#text']=node.text or ''
  for key in values:
   if key not in headers:headers.append(key)
  if len(headers)>250:raise ValueError('DOCUMENT_XML_LIMIT')
  dictionaries.append(values)
 from importers import table
 rows=[headers]+[[values.get(key,'') for key in headers] for values in dictionaries]
 result=table(Path(source['name']).stem,rows,{'format':'xml','encoding':'XML declaration/BOM','headerRow':1,'xmlRecordPath':selected,'emptyPolicy':'Absent and empty elements share blank in the working table; original XML preserves their distinction.'},['Explicit record path; attributes use @ and plain element text remains literal. Whitespace, zeros, missing-token literals and namespaces are not normalized. Original XML retains absent/empty distinctions and all context.'])
 archaeology['xml']['selectedRecordPath']=selected;return [result],archaeology

W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
def word_text(node):
 pieces=[]
 for child in node.iter():
  if child.tag in [W+'t',W+'delText']:pieces.append(child.text or '')
  elif child.tag==W+'tab':pieces.append('\t')
  elif child.tag in [W+'br',W+'cr']:pieces.append('\n')
 return ''.join(pieces)

def docx(source,options):
 with safe_archive(source_bytes(source)) as archive:
  if any(member.flag_bits&1 for member in archive.infolist()):raise ValueError('DOCUMENT_WORD_ENCRYPTED')
  if 'word/document.xml' not in archive.namelist():raise ValueError('DOCUMENT_WORD_PART')
  root,node_count=xml_tree(archive.read('word/document.xml'));body=root.find(W+'body')
  if body is None:raise ValueError('DOCUMENT_WORD_PART')
  blocks=[];changes=[];paragraph=0;tables=0;omitted=0;total_characters=0;total_changes=0;unsupported=Counter()
  for child in body:
   if child.tag not in [W+'p',W+'tbl']:unsupported[child.tag]+=1;continue
   kind='paragraph' if child.tag==W+'p' else 'table';paragraph+=kind=='paragraph';tables+=kind=='table'
   if kind=='paragraph':value=word_text(child);record={'kind':kind,'paragraph':paragraph,'text':value[:4000],'truncated':len(value)>4000}
   else:
    rows=[]
    for row in child.findall(W+'tr')[:20]:rows.append([word_text(cell)[:1000] for cell in row.findall(W+'tc')[:20]])
    record={'kind':kind,'table':tables,'rows':rows,'truncated':len(child.findall(W+'tr'))>20 or any(len(row.findall(W+'tc'))>20 or any(len(word_text(cell))>1000 for cell in row.findall(W+'tc')) for row in child.findall(W+'tr'))}
   for change in child.iter():
    if change.tag in [W+'ins',W+'del']:
     total_changes+=1
     if len(changes)<200:
      change_text=word_text(change);changes.append({'blockKind':kind,'block':paragraph if kind=='paragraph' else tables,'kind':'inserted' if change.tag==W+'ins' else 'deleted','author':change.get(W+'author','')[:200],'date':change.get(W+'date','')[:100],'text':change_text[:2000],'truncated':len(change_text)>2000})
   length=len(json.dumps(record,ensure_ascii=False))
   if len(blocks)<200 and total_characters+length<=200000:blocks.append(record);total_characters+=length
   else:omitted+=1
  comments=[];total_comments=0
  if 'word/comments.xml' in archive.namelist():
   comment_root,_=xml_tree(archive.read('word/comments.xml'))
   all_comments=comment_root.findall(W+'comment');total_comments=len(all_comments)
   for comment in all_comments[:200]:
    comment_text=word_text(comment);comments.append({'id':comment.get(W+'id',''),'author':comment.get(W+'author','')[:200],'date':comment.get(W+'date','')[:100],'text':comment_text[:4000],'truncated':len(comment_text)>4000})
  return [],{'documentPreview':{'kind':'word','blocks':blocks,'bounded':True,'totalParagraphs':paragraph,'totalTables':tables,'omittedBlocks':omitted,'trackedChanges':changes,'comments':comments,'totalTrackedChanges':total_changes,'totalComments':total_comments,'omittedTrackedChanges':total_changes-len(changes),'omittedComments':total_comments-len(comments),'unsupportedBodyNodes':dict(unsupported),'notes':['Passive excerpt preview, not a reconstructed Word document or stable pagination. Tracked insertions and deletions both appear in text and are listed separately; review the original before quoting meaning. Excerpts are limited to 200 blocks / 200,000 characters, 4,000 characters per paragraph, and 20×20 cells per table.','Formatting, images, headers, footers, footnotes, content controls, embedded files, macros and external links remain in the original. Nothing is executed or fetched. No metadata meaning is automatically confirmed.']},'container':{'members':len(archive.infolist()),'macroPartsPresent':any(name.lower().endswith('vbaproject.bin') for name in archive.namelist())},'xmlNodes':node_count}

class BoundedReader:
 def __init__(self,source):self.source=source;self.total=0
 def read(self,size):
  block=self.source.read(min(size,100*1024*1024-self.total+1));self.total+=len(block)
  if self.total>100*1024*1024:raise ValueError('DOCUMENT_TAR_LIMIT')
  return block
def tar(source,options):
 data=source_bytes(source);compressed=data[:2]==b'\x1f\x8b';stream=gzip.GzipFile(fileobj=io.BytesIO(data)) if compressed else io.BytesIO(data);members=[];seen=set();total=0
 try:
  with tarfile.open(fileobj=BoundedReader(stream),mode='r|') as archive:
   for member in archive:
    total+=member.size
    if len(members)>=1000 or member.size>20*1024*1024 or total>100*1024*1024:raise ValueError('DOCUMENT_TAR_LIMIT')
    path=PurePosixPath(member.name);unsafe=not member.name or path.is_absolute() or '..' in path.parts or ':' in member.name or '\\' in member.name
    members.append({'name':member.name,'bytes':member.size,'kind':'file' if member.isfile() else 'directory' if member.isdir() else 'symbolic link' if member.issym() else 'hard link' if member.islnk() else 'special','linkTarget':member.linkname,'unsafePath':unsafe,'duplicateName':member.name in seen,'modifiedUnixTime':member.mtime});seen.add(member.name)
 finally:stream.close()
 return [],{'members':members,'expandedPayloadBytes':total,'compressed':compressed,'notes':['Passive TAR inventory only; no member, link or special file is extracted or executed. Unsafe paths and duplicate names remain visible. Original archive bytes retain all members.']}
