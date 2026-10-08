"""Passive MS-DOC main-story evidence, not document reconstruction.

Offsets and compressed text follow Microsoft's MS-DOC FIB/CLX/PlcPcd/FcCompressed
specification. Properties, fields, macros, revisions and external content are not
interpreted or executed. Every candidate piece is checked before any preview.
"""
import io,json,struct,sys
from pathlib import Path

VERSIONS={0xC1:(93,0),0xD9:(108,2),0x101:(136,2),0x10C:(164,2),0x112:(183,5)}
SPECIAL={0x82:0x201A,0x83:0x0192,0x84:0x201E,0x85:0x2026,0x86:0x2020,0x87:0x2021,0x88:0x02C6,0x89:0x2030,0x8A:0x0160,0x8B:0x2039,0x8C:0x0152,0x91:0x2018,0x92:0x2019,0x93:0x201C,0x94:0x201D,0x95:0x2022,0x96:0x2013,0x97:0x2014,0x98:0x02DC,0x99:0x2122,0x9A:0x0161,0x9B:0x203A,0x9C:0x0153,0x9F:0x0178}
MAX_INPUT=20*1024*1024

def bounded(data,start,size):
 if start<0 or size<0 or start+size>len(data):raise ValueError('DOC_BOUNDS')
 return data[start:start+size]

def u16(data,offset):return struct.unpack('<H',bounded(data,offset,2))[0]
def u32(data,offset):return struct.unpack('<I',bounded(data,offset,4))[0]

def literal_display(text):
 return ''.join(f'⟦U+{ord(c):04X}⟧' if ord(c)<32 and c not in '\t\n' or 0x7F<=ord(c)<=0x9F or 0x202A<=ord(c)<=0x202E or 0x2066<=ord(c)<=0x2069 else c for c in text)

def read_story(word,table):
 if u16(word,0)!=0xA5EC:raise ValueError('DOC_FIB')
 flags=u16(word,10)
 if flags&0x100:raise ValueError('DOC_ENCRYPTED')
 if not flags&0x1000:raise ValueError('DOC_VERSION')
 base_version=u16(word,2)
 if base_version not in VERSIONS:raise ValueError('DOC_VERSION')
 offset=32;csw=u16(word,offset);offset+=2
 if csw!=14:raise ValueError('DOC_FIB')
 bounded(word,offset,csw*2);offset+=csw*2
 cslw=u16(word,offset);offset+=2
 if cslw!=22:raise ValueError('DOC_FIB')
 longs=struct.unpack('<22I',bounded(word,offset,cslw*4));offset+=cslw*4
 pair_count=u16(word,offset);offset+=2
 pairs=bounded(word,offset,pair_count*8);offset+=pair_count*8
 new_count=u16(word,offset);offset+=2
 extension=bounded(word,offset,new_count*2);offset+=new_count*2
 version=u16(extension,0) if new_count else base_version
 if version not in VERSIONS:raise ValueError('DOC_VERSION')
 if (pair_count,new_count)!=VERSIONS[version]:raise ValueError('DOC_FIB')
 cb_mac=longs[0];main=longs[3];other=[longs[i] for i in (4,5,7,8,9,10)]
 if cb_mac<offset or cb_mac>len(word):raise ValueError('DOC_BOUNDS')
 if main>1000000 or sum(other)+main>2000000:raise ValueError('DOC_LIMIT')
 fc_clx=u32(pairs,33*8);lcb_clx=u32(pairs,33*8+4)
 if lcb_clx==0 or lcb_clx>1024*1024:raise ValueError('DOC_PIECES')
 clx=bounded(table,fc_clx,lcb_clx);p=0;property_records=0
 while p<len(clx) and clx[p]==1:
  size=struct.unpack('<h',bounded(clx,p+1,2))[0]
  if not 0<=size<=0x3FA2:raise ValueError('DOC_PIECES')
  bounded(clx,p+3,size);p+=3+size;property_records+=1
  if property_records>10000:raise ValueError('DOC_LIMIT')
 if bounded(clx,p,1)!=b'\x02':raise ValueError('DOC_PIECES')
 size=u32(clx,p+1);plc=bounded(clx,p+5,size)
 if p+5+size!=len(clx) or size<4 or (size-4)%12:raise ValueError('DOC_PIECES')
 count=(size-4)//12
 if count>10000:raise ValueError('DOC_LIMIT')
 cps=struct.unpack('<'+str(count+1)+'I',plc[:4*(count+1)])
 expected_last=main+sum(other)+(1 if any(other) else 0)
 if cps[0]!=0 or cps[-1]!=expected_last or any(a>=b for a,b in zip(cps,cps[1:])):raise ValueError('DOC_PIECES')
 pieces=[];raw=bytearray()
 for i in range(count):
  pcd=bounded(plc,4*(count+1)+8*i,8);fc=u32(pcd,2);compressed=bool(fc&0x40000000);location=fc&0x3FFFFFFF
  if compressed and location%2:raise ValueError('DOC_BOUNDS')
  location=location//2 if compressed else location
  characters=cps[i+1]-cps[i];byte_count=characters*(1 if compressed else 2)
  if location<offset or location+byte_count>cb_mac:raise ValueError('DOC_BOUNDS')
  data=bounded(word,location,byte_count);take=max(0,min(cps[i+1],main)-cps[i])
  if take:
   data=data[:take*(1 if compressed else 2)]
   raw.extend(''.join(chr(SPECIAL.get(n,n)) for n in data).encode('utf-16-le') if compressed else data)
  pieces.append({'piece':i+1,'cpStart':cps[i],'cpEnd':cps[i+1],'wordByteOffset':location,'bytes':byte_count,'encoding':'MS-DOC compressed Unicode mapping' if compressed else 'UTF-16LE','mainStoryCharacters':take})
 try:text=bytes(raw).decode('utf-16-le',errors='strict')
 except UnicodeDecodeError:raise ValueError('DOC_TEXT') from None
 if len(raw)!=main*2 or main and not text.endswith('\r'):raise ValueError('DOC_TEXT')
 blocks=[];cp=0;used=0;omitted=0;paragraphs=text.split('\r')
 if text.endswith('\r'):paragraphs.pop()
 if not main:paragraphs=[]
 for index,paragraph in enumerate(paragraphs):
  paragraph+='\r';length=len(paragraph.encode('utf-16-le'))//2
  excerpt=paragraph[:4000];excerpt_units=len(excerpt.encode('utf-16-le'))//2
  if len(blocks)<200 and used+len(excerpt)<=150000:
   blocks.append({'kind':'legacy-doc-text','paragraph':index+1,'cpStart':cp,'cpEnd':cp+length,'previewCpEnd':cp+excerpt_units,'rawText':excerpt,'text':literal_display(excerpt),'truncated':len(excerpt)<len(paragraph)})
   used+=len(excerpt)
  else:omitted+=1
  cp+=length
 return {'kind':'legacy-doc','blocks':blocks,'bounded':True,'mainStoryCpCount':main,'previewCharacters':used,'totalParagraphMarks':text.count('\r'),'omittedBlocks':omitted,'fibVersion':hex(version),'baseFibVersion':hex(base_version),'tableStream':'1Table' if flags&0x200 else '0Table','pieces':pieces,'otherStoryCpCounts':dict(zip(['footnotes','headersFooters','comments','endnotes','textboxes','headerTextboxes'],other)),'skippedPropertyRecords':property_records,'legacyWord':{'mainStoryOnly':True,'propertiesInterpreted':False,'revisionsResolved':False,'macrosExecuted':False,'externalContentFetched':False,'faithfulDocumentReconstruction':False},'limits':{'maxMainStoryCp':1000000,'maxTotalStoryCp':2000000,'maxPieces':10000,'maxBlocks':200,'maxPreviewCharacters':150000,'maxCharactersPerBlock':4000}}

def inspect(path):
 from pdf_limits import child_limits
 try:mechanism=child_limits()
 except ValueError:raise ValueError('DOC_LIMIT_UNAVAILABLE') from None
 data=Path(path).read_bytes()
 if len(data)>MAX_INPUT:raise ValueError('DOC_LIMIT')
 if bounded(data,0,8)!=b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1':raise ValueError('DOC_CONTAINER')
 if u16(data,26)!=3 or u16(data,30)!=9 or u16(data,32)!=6:raise ValueError('DOC_CONTAINER')
 sys.path.insert(0,str(Path(__file__).resolve().parent/'vendor-xls'))
 from xlrd.compdoc import CompDoc
 log=io.StringIO();compound=CompDoc(data,logfile=log,ignore_workbook_corruption=False)
 if len(compound.dirlist)>1000:raise ValueError('DOC_LIMIT')
 names=[entry.name for entry in compound.dirlist if entry.parent==0 and entry.etype==2]
 if len(names)!=len(set(name.casefold() for name in names)):raise ValueError('DOC_CONTAINER')
 word=compound.get_named_stream('WordDocument')
 if word is None:raise ValueError('DOC_FIB')
 if u16(word,10)&0x100:raise ValueError('DOC_ENCRYPTED')
 table_name='1Table' if u16(word,10)&0x200 else '0Table'
 table=compound.get_named_stream(table_name)
 if table is None:raise ValueError('DOC_TABLE_STREAM')
 result=read_story(word,table)
 if log.getvalue():raise ValueError('DOC_CONTAINER')
 result['containerEntries']=[{'name':e.name,'kind':'stream' if e.etype==2 else 'storage','bytes':e.tot_size if e.etype==2 else None} for e in compound.dirlist if e.etype in (1,2)]
 result['reader']={'container':'xlrd.compdoc','containerVersion':'2.0.2','textPolicy':'ms-doc-main-story-v1'}
 result['limits'].update({'memoryBytes':256*1024*1024,'wallSeconds':20,'maxInputBytes':MAX_INPUT,'maxWorkerOutputBytes':4*1024*1024,'mechanism':mechanism})
 return result

if __name__=='__main__':
 if sys.stdin.readline().strip()!='go':raise SystemExit(2)
 try:result=inspect(sys.argv[1])
 except MemoryError:result={'error':'DOC_MEMORY_LIMIT'}
 except ValueError as error:result={'error':str(error) if str(error).startswith('DOC_') else 'DOC_INVALID'}
 except Exception:result={'error':'DOC_INVALID'}
 encoded=json.dumps(result,ensure_ascii=False).encode('utf-8')
 if len(encoded)>4*1024*1024:encoded=b'{"error":"DOC_OUTPUT_LIMIT"}'
 sys.stdout.buffer.write(encoded)
