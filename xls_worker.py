"""One-shot passive legacy Excel extraction, with input gate and OS limits."""
import io,json,math,sys
from pathlib import Path


def inspect(path, options):
 from pdf_limits import child_limits
 try:mechanism=child_limits()
 except ValueError:raise ValueError('XLS_LIMIT_UNAVAILABLE') from None
 sys.path.insert(0,str(Path(__file__).resolve().parent/'vendor-xls'))
 import xlrd
 header=options.get('headerRow',1);by_sheet=options.get('headersBySheet',{})
 if type(header) is not int or not 1<=header<=1000 or not isinstance(by_sheet,dict) or any(type(n) is not int or not 1<=n<=1000 for n in by_sheet.values()):raise ValueError('XLS_OPTIONS')
 encoding=options.get('encoding','auto')
 if encoding not in ('auto','utf-8','utf-8-sig','utf-16','cp1252','latin-1'):raise ValueError('XLS_OPTIONS')
 encoding=None if encoding=='auto' else 'utf-8' if encoding=='utf-8-sig' else encoding
 book=xlrd.open_workbook(filename=path,logfile=io.StringIO(),use_mmap=False,on_demand=True,formatting_info=True,ragged_rows=False,encoding_override=encoding,ignore_workbook_corruption=False)
 try:
  if book.nsheets>100:raise ValueError('XLS_LIMIT')
  tables=[];sheets=[];cells=0;characters=0
  for i,name in enumerate(book.sheet_names()):
   sheet=book.sheet_by_index(i);h=by_sheet.get(name,header)
   if sheet.nrows>100000 or sheet.ncols>250:raise ValueError('XLS_LIMIT')
   cells+=sheet.nrows*sheet.ncols
   if cells>500000:raise ValueError('XLS_LIMIT')
   rows=[];types=[];counts={};date_cells=[];error_cells=[];dates=errors=0
   for row in range(sheet.nrows):
    values=[];row_types=[]
    for col in range(sheet.ncols):
     cell=sheet.cell(row,col);kind=cell.ctype;value=cell.value
     if isinstance(value,float) and not math.isfinite(value):raise ValueError('XLS_NONFINITE')
     value='' if kind in (xlrd.XL_CELL_EMPTY,xlrd.XL_CELL_BLANK) else str(value)
     characters+=len(value)
     if len(value)>1000000 or characters>10000000:raise ValueError('XLS_LIMIT')
     values.append(value);row_types.append(kind);counts[str(kind)]=counts.get(str(kind),0)+1
     if kind==xlrd.XL_CELL_DATE:
      dates+=1
      if len(date_cells)<500:date_cells.append({'row':row+1,'column':col+1,'serial':value,'numberFormat':book.format_map[book.xf_list[cell.xf_index].format_key].format_str})
     if kind==xlrd.XL_CELL_ERROR:
      errors+=1
      if len(error_cells)<500:error_cells.append({'row':row+1,'column':col+1,'code':value,'label':xlrd.error_text_from_code.get(cell.value,'Unknown Excel error')})
    rows.append(values);types.append(row_types)
   empty=sheet.nrows==0 or sheet.ncols==0
   if not empty and h>len(rows):raise ValueError('XLS_HEADER')
   facts={'name':name,'state':['visible','hidden','very-hidden'][sheet.visibility] if sheet.visibility in (0,1,2) else str(sheet.visibility),'rows':sheet.nrows,'columns':sheet.ncols,'cellTypes':types,'cellTypeCounts':counts,'dateCells':date_cells,'omittedDateCellLocations':dates-len(date_cells),'errorCells':error_cells,'omittedErrorCellLocations':errors-len(error_cells),'mergedCells':[list(bounds) for bounds in sheet.merged_cells],'hiddenRows':[n+1 for n,info in sheet.rowinfo_map.items() if info.hidden],'hiddenColumns':[n+1 for n,info in sheet.colinfo_map.items() if info.hidden],'headerRow':h,'empty':empty}
   sheets.append(facts)
   if not empty:tables.append({'name':name,'rows':rows,'headerRow':h})
   book.unload_sheet(i)
  return {'tables':tables,'archaeology':{'sheets':sheets,'dateSystem':'1904' if book.datemode else '1900','biffVersion':book.biff_version,'encoding':book.encoding,'reader':{'name':'xlrd','version':xlrd.__version__,'strictCorruption':True},'cellTypeCodes':{'0':'empty','1':'text','2':'number','3':'date serial','4':'boolean code','5':'error code','6':'formatted blank'},'limits':{'memoryBytes':256*1024*1024,'wallSeconds':20,'maxSheets':100,'maxRowsPerSheet':100000,'maxColumns':250,'maxCells':500000,'maxValueCharacters':10000000,'maxWorkerOutputBytes':20*1024*1024,'mechanism':mechanism},'legacyExcel':{'cachedValuesOnly':True,'dateSerialsUnchanged':True,'formulasRecalculated':False,'macrosExecuted':False,'faithfulWorkbookReconstruction':False},'notes':['Extracted cached cell values only. Formula text and formula provenance are not recovered; caches may be absent or stale. Dates remain numerical serials and require explicit interpretation using the recorded date system.','Numeric values are shortest round-trip representations of the recovered binary floating-point value, not displayed workbook text. Boolean/error codes remain literal and cell type codes are retained. Number formats, merged cells and hidden records do not establish scientific meanings.','Charts, macros, comments, hyperlinks, external connections and embedded objects are not executed or converted. Review the exact original workbook for context and layout.']}}
 finally:book.release_resources()


if __name__=='__main__':
 if sys.stdin.readline().strip()!='go':raise SystemExit(2)
 try:result=inspect(sys.argv[1],json.loads(sys.stdin.readline()))
 except MemoryError:result={'error':'XLS_MEMORY_LIMIT'}
 except ValueError as error:result={'error':str(error) if str(error).startswith('XLS_') else 'XLS_INVALID'}
 except Exception:result={'error':'XLS_INVALID'}
 encoded=json.dumps(result,ensure_ascii=False).encode('utf-8')
 if len(encoded)>20*1024*1024:encoded=b'{"error":"XLS_OUTPUT_LIMIT"}'
 sys.stdout.buffer.write(encoded)
