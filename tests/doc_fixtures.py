"""Fictional structural fixtures; not a full Word document authoring library."""
import math,struct

def ole(word,table,table_name='1Table'):
 streams=[(table_name,table),("WordDocument",word)];chunks=[];starts=[];fat=[]
 for name,data in streams:
  data=data.ljust(max(4096,math.ceil(len(data)/512)*512),b'\0');starts.append((len(chunks),len(data)));n=len(data)//512
  for i in range(n):fat.append(len(chunks)+1 if i<n-1 else -2);chunks.append(data[i*512:(i+1)*512])
 directory_sector=len(chunks);fat.append(-2);fat_sector=directory_sector+1;fat.append(-3)
 def entry(name,kind,left=-1,right=-1,child=-1,start=-2,size=0):
  e=bytearray(128);label=(name+'\0').encode('utf-16-le');e[:len(label)]=label;struct.pack_into('<HBBiii',e,64,len(label),kind,1,left,right,child);struct.pack_into('<iQ',e,116,start,size);return e
 directory=entry('Root Entry',5,child=1)+entry(streams[0][0],2,right=2,start=starts[0][0],size=starts[0][1])+entry(streams[1][0],2,start=starts[1][0],size=starts[1][1])+bytearray(128)
 header=bytearray(512);header[:8]=b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1';struct.pack_into('<HHHHH',header,24,0x3E,3,0xFFFE,9,6);struct.pack_into('<IIIIIIIII',header,40,0,1,directory_sector,0,4096,0xFFFFFFFE,0,0xFFFFFFFE,0);struct.pack_into('<109i',header,76,fat_sector,*([-1]*108))
 assert len(fat)<=128
 return bytes(header)+b''.join(chunks)+bytes(directory)+struct.pack('<128i',*fat,*([-1]*(128-len(fat))))

def streams(parts=None,version=0xC1,encrypted=False,properties=b''):
 from doc_worker import VERSIONS
 parts=parts or [('Fictional wetland: 0, NA and -999 remain literal.\r',True),('湿地 · Frog 🐸\r',False),('Field controls: \x13LINK fictional\x14literal\x15\r',True)]
 count,new_count=VERSIONS[version];word=bytearray(4096);struct.pack_into('<HH',word,0,0xA5EC,0xC1);struct.pack_into('<H',word,10,0x1200|(0x100 if encrypted else 0));struct.pack_into('<H',word,32,14);struct.pack_into('<H',word,62,22);struct.pack_into('<H',word,152,count)
 end=154+8*count;struct.pack_into('<H',word,end,new_count)
 if new_count:struct.pack_into('<H',word,end+2,version)
 text_at=max(2048,end+2+2*new_count);cps=[0];pcds=[]
 for text,compressed in parts:
  raw=text.encode('latin-1') if compressed else text.encode('utf-16-le');units=len(raw) if compressed else len(raw)//2
  word[text_at:text_at+len(raw)]=raw;pcds.append(struct.pack('<HIH',0,(text_at*2|0x40000000) if compressed else text_at,0));text_at+=len(raw);cps.append(cps[-1]+units)
 struct.pack_into('<I',word,64,text_at);struct.pack_into('<I',word,76,cps[-1]);plc=struct.pack('<'+str(len(cps))+'I',*cps)+b''.join(pcds);clx=properties+b'\x02'+struct.pack('<I',len(plc))+plc;struct.pack_into('<II',word,154+33*8,0,len(clx))
 return bytes(word),clx

def fixture(**kwargs):
 word,table=streams(**kwargs);return ole(word,table)
