"""Reviewed decoded-character widths; literal slices without inferred boundaries."""
import io
from pathlib import Path
from rescue import source_bytes,shape,MAX_COLS,MAX_ROWS
ERRORS={
 'FW_WIDTHS':'Enter 1–250 positive whole-number widths with a total of at most 65,536 characters. The original remains preserved.',
 'FW_ENCODING':'Choose an explicit text encoding before fixed-width conversion. The original remains preserved.',
 'FW_HEADER':'Choose header row 0 for no header, or a header row from 1–1,000 within the file. The original remains preserved.',
 'FW_NUL':'Decoded text contains NUL characters. Review the source encoding; the original remains preserved.',
 'FW_ROWS':'Fixed-width conversion exceeds 100,000 data records. The original remains preserved.',
 'FW_LENGTH':'A selected line does not match the reviewed total width. No padding, truncation or partial table was applied; the original remains preserved.'}

def fixed_width(source,options):
 widths=options.get('fixedWidths')
 if not isinstance(widths,list) or not 1<=len(widths)<=MAX_COLS or any(type(w) is not int or not 1<=w<=65536 for w in widths) or sum(widths)>65536:raise ValueError('FW_WIDTHS')
 encoding=options.get('encoding')
 if encoding not in ['utf-8','utf-8-sig','utf-16','cp1252','latin-1']:raise ValueError('FW_ENCODING')
 header=options.get('headerRow',1)
 if type(header) is not int or not 0<=header<=1000:raise ValueError('FW_HEADER')
 decoded=source_bytes(source).decode(encoding,errors='strict')
 if '\x00' in decoded:raise ValueError('FW_NUL')
 start=header-1 if header else 0
 rows=[];expected=sum(widths)
 for index,line in enumerate(io.StringIO(decoded,newline='')):
  if index<start:continue
  if len(rows)>=MAX_ROWS+(1 if header else 0):raise ValueError('FW_ROWS')
  if line.endswith('\r\n'):line=line[:-2]
  elif line.endswith(('\r','\n')):line=line[:-1]
  if len(line)!=expected:raise ValueError('FW_LENGTH')
  offset=0;row=[]
  for width in widths:row.append(line[offset:offset+width]);offset+=width
  rows.append(row)
 if not rows:raise ValueError('FW_HEADER')
 if header:headers,values,row_widths,original=shape(rows,1)
 else:headers=[f'column_{i+1}' for i in range(len(widths))];values=rows;row_widths=[len(widths)]*len(rows);original=[]
 recipe={'format':'fixed-width','encoding':encoding,'fixedWidths':widths,'offsetUnit':'decoded Unicode code points','headerRow':header,'preambleLines':start,'adapterVersion':1,'lineSeparatorPolicy':'CRLF, LF or CR; one final terminator is structural','stripValues':False,'lengthPolicy':'exact reviewed total width on every selected record'}
 notes=['Character widths are explicit human choices, not inferred byte offsets or displayed column widths. Tabs and combining characters count as individual decoded code points. Whitespace, leading zeros, zero and NA are literal. Every selected record must match the full width; no padding, truncation or skipped blank records. Preamble and line endings remain in the original. Header row 0 generates neutral field names and keeps the first record.']
 return [{'name':Path(source['name']).stem,'sheet':None,'headers':headers,'rows':values,'rowWidths':row_widths,'originalHeaders':original,'parsing':recipe,'notes':notes}],{'fixedWidthReview':{'widths':widths,'encoding':encoding,'headerRow':header,'boundaryMeaning':'unconfirmed human-entered character widths'},'notes':notes}
