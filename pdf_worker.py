"""Private one-shot PDF excerpt worker; input gate precedes parsing."""
import json,logging,sys
from pathlib import Path
def inspect(path):
 from pdf_limits import child_limits
 limitation=child_limits();sys.path.insert(0,str(Path(__file__).resolve().parent/'vendor'))
 from pypdf import PdfReader,__version__
 logging.getLogger('pypdf').disabled=True;reader=PdfReader(path,strict=True)
 if reader.is_encrypted:return {'error':'PDF_ENCRYPTED'}
 count=len(reader.pages)
 if count>2000:return {'error':'PDF_PAGE_LIMIT'}
 metadata=reader.metadata or {};document_info={key:str(metadata[key])[:1000] for key in ['/Title','/Author','/Subject','/Creator','/Producer','/CreationDate','/ModDate'] if key in metadata};blocks=[];characters=0;no_text=0
 for index in range(min(count,50)):
  if characters>=150000:break
  page=reader.pages[index];value=page.extract_text() or '';excerpt=value[:min(4000,150000-characters)];characters+=len(excerpt);no_text+=not value.strip();blocks.append({'kind':'page','page':index+1,'text':excerpt,'truncated':len(excerpt)!=len(value),'noRecoveredText':not value.strip()})
 return {'kind':'pdf','blocks':blocks,'bounded':True,'totalPages':count,'previewPages':len(blocks),'omittedPages':count-len(blocks),'previewPagesWithoutRecoveredText':no_text,'documentProperties':document_info,'reader':{'name':'pypdf','version':__version__,'strict':True},'limits':{'memoryBytes':256*1024*1024,'wallSeconds':20,'maxPages':50,'maxCharacters':150000,'maxCharactersPerPage':4000,'mechanism':limitation},'notes':['Bounded text-layer excerpts with physical PDF page references. Reading order, spacing, glyphs and prior OCR text can be inaccurate. This is not OCR or reconstructed table layout. Review the original before scientific interpretation.','Protected documents, unsupported content and time/memory-limit failures remain preserved without recovered text. JavaScript, actions, external links and embedded attachments are not executed, fetched or extracted.']}
if __name__=='__main__':
 if sys.stdin.readline().strip()!='go':raise SystemExit(2)
 try:result=inspect(sys.argv[1])
 except MemoryError:result={'error':'PDF_MEMORY_LIMIT'}
 except ValueError as error:result={'error':str(error) if str(error).startswith('PDF_') else 'PDF_INVALID'}
 except Exception:
  import os
  if os.environ.get('WORKBENCH_WORKER_DIAGNOSTICS')=='1':
   import traceback
   traceback.print_exc(file=sys.stderr)
  result={'error':'PDF_INVALID'}
 encoded=json.dumps(result,ensure_ascii=False).encode('utf-8')
 if len(encoded)>1024*1024:encoded=b'{"error":"PDF_OUTPUT_LIMIT"}'
 sys.stdout.buffer.write(encoded)
