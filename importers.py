from xls_import import xls
"""Versioned import adapters. Unsupported bytes are preserved as evidence resources."""
import base64
import io
import json
import sqlite3
import tempfile
import zipfile
import tarfile
from pathlib import Path
from datetime import datetime, timezone
from xml.etree import ElementTree as ET
from rescue import source_bytes, sha, inspect, shape, NS, REL, MAX_ROWS, MAX_COLS

ADAPTER_VERSION = 1


def literal(value):
    if value is None:
        return ''
    if isinstance(value, bytes):
        return 'base64:' + base64.b64encode(value).decode()
    if isinstance(value, (dict, list, bool)):
        return json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    return str(value)


def table(name, rows, parsing, notes=None):
    headers, values, widths, original = shape(rows, int(parsing.get('headerRow', 1)))
    return {'name': name, 'sheet': parsing.get('sheet'), 'headers': headers, 'rows': values, 'rowWidths': widths, 'originalHeaders': original, 'parsing': {**parsing, 'adapterVersion': ADAPTER_VERSION}, 'notes': notes or []}


def excel_archaeology(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if sum(i.file_size for i in z.infolist()) > 100 * 1024 * 1024:
            raise ValueError('Expanded workbook exceeds 100 MiB.')
        def xml(path):
            data = z.read(path)
            if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
                raise ValueError('XML entity declarations are unsupported.')
            return ET.fromstring(data)
        book = xml('xl/workbook.xml')
        rels = {r.attrib['Id']: r.attrib['Target'] for r in xml('xl/_rels/workbook.xml.rels') if r.attrib.get('TargetMode') != 'External'}
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            shared=[''.join(t.text or '' for t in si.findall('.//s:t',NS)) for si in xml('xl/sharedStrings.xml').findall('s:si',NS)]
        sheets=[]
        for sheet in book.findall('s:sheets/s:sheet',NS):
            target=rels.get(sheet.attrib.get(f'{{{REL}}}id'))
            if not target:
                sheets.append({'name':sheet.attrib['name'],'state':sheet.attrib.get('state','visible'),'unsupported':'External or unsupported sheet target'}); continue
            import posixpath
            target=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            if not target.startswith('xl/'):
                raise ValueError('Invalid worksheet location.')
            root=xml(target)
            formulas=[];preview=[];blank=[];widths=[];occupied_rows=[]
            for row in root.findall('s:sheetData/s:row',NS):
                widths.append(len(row.findall('s:c',NS)))
                occupied_rows.append(int(row.attrib.get('r',len(widths))))
                values=[]
                for c in row.findall('s:c',NS):
                    value=c.findtext('s:v',default='',namespaces=NS)
                    if c.attrib.get('t')=='s' and value:value=shared[int(value)]
                    if c.attrib.get('t')=='inlineStr':value=''.join(t.text or '' for t in c.findall('.//s:t',NS))
                    values.append(value)
                    formula=c.find('s:f',NS)
                    if formula is not None:formulas.append({'cell':c.attrib.get('r'),'formula':formula.text or '', 'attributes':formula.attrib, 'cachedValue':value})
                if not any(values):blank.append(row.attrib.get('r'))
                if len(preview)<12:preview.append({'row':row.attrib.get('r'),'values':values})
            merges=[m.attrib.get('ref') for m in root.findall('s:mergeCells/s:mergeCell',NS)]
            comments=[]
            rel_path=posixpath.dirname(target)+'/_rels/'+posixpath.basename(target)+'.rels'
            if rel_path in z.namelist():
                for rel in xml(rel_path):
                    if rel.attrib.get('Type','').endswith('/comments') and rel.attrib.get('TargetMode')!='External':
                        comment_path=posixpath.normpath(posixpath.dirname(target)+'/'+rel.attrib['Target'])
                        if comment_path.startswith('xl/') and comment_path in z.namelist():
                            cr=xml(comment_path)
                            authors=[a.text or '' for a in cr.findall('s:authors/s:author',NS)]
                            for comment in cr.findall('s:commentList/s:comment',NS):
                                author=int(comment.attrib.get('authorId',0));comments.append({'cell':comment.attrib.get('ref'),'author':authors[author] if author<len(authors) else '', 'text':''.join(t.text or '' for t in comment.findall('.//s:t',NS))})
            sheets.append({'name':sheet.attrib['name'],'state':sheet.attrib.get('state','visible'),'formulas':formulas,'comments':comments,'mergedCells':merges,'firstRows':preview,'blankRows':blank,'occupiedRowNumbers':occupied_rows,'irregularCellCounts':len(set(widths))>1,'headerCandidates':[r['row'] for r in preview if len([v for v in r['values'] if v])>=2][:5]})
        props=book.find('s:workbookPr',NS)
        return {'sheets':sheets,'dateSystem':'1904' if props is not None and props.attrib.get('date1904') in ('1','true') else '1900','unsupported':['Formatting, charts, images, threaded comments, pivot tables, external links and embedded objects remain in the original workbook; not converted to tabular data.','Header candidates are suggestions only. Multiple header bands and preamble rows need explicit human selection.']}


def import_delimited(source, options):
    result=inspect({'source':source,'options':options})
    t={k:result[k] for k in ('headers','rows','rowWidths','originalHeaders','parsing','notes')}
    t['name']=Path(source['name']).stem;t['sheet']=None
    t['parsing'].update({'adapterVersion':ADAPTER_VERSION,'quoteChar':'"','doubleQuote':True,'escapeChar':None,'skipInitialSpace':False,'strict':True})
    return [t],{'notes':result['notes']}


def import_xlsx(source, options):
    archaeology=excel_archaeology(source_bytes(source, allow_empty=True));tables=[]
    for sheet in archaeology['sheets']:
        try:
            result=inspect({'source':source,'options':{**options,'sheet':sheet['name'],'headerRow':options.get('headersBySheet',{}).get(sheet['name'],options.get('headerRow',1))}})
            t={k:result[k] for k in ('headers','rows','rowWidths','originalHeaders','parsing','notes')};t['name']=sheet['name'];t['sheet']=sheet['name'];t['parsing']['adapterVersion']=ADAPTER_VERSION
            tables.append(t)
        except ValueError as exc:
            sheet['conversionIssue']=str(exc)
    return tables,archaeology


def import_json(source, options):
    data=json.loads(source_bytes(source, allow_empty=True).decode('utf-8-sig'))
    collections={'records':data} if isinstance(data,list) else data if isinstance(data,dict) else {}
    tables=[];notes=[]
    for name,records in collections.items():
        if not isinstance(records,list) or not records or not all(isinstance(r,dict) for r in records):
            notes.append(f'{name}: not a nonempty array of records; retained in original JSON.');continue
        headers=list(dict.fromkeys(k for r in records for k in r));rows=[[literal(r.get(k)) for k in headers] for r in records]
        tables.append(table(str(name),[headers,*rows],{'format':'json','encoding':'utf-8','headerRow':1},['Nested values serialized as JSON strings; null becomes a blank in working CSV. Original JSON distinguishes null from absent keys.']))
    return tables,{'notes':notes}


def import_sqlite(source, options):
    data=source_bytes(source, allow_empty=True);tables=[];notes=['SQLite imported read-only. Views/triggers are not executed. Blob values retained as base64 text. GeoPackage geometry is preserved, not mapped or converted.']
    with tempfile.TemporaryDirectory(prefix='biorescue-') as directory:
        path=Path(directory)/'source.sqlite';path.write_bytes(data)
        conn=sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True)
        try:
            conn.execute('PRAGMA query_only=ON')
            names=[r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            if len(names)>100:raise ValueError('Database exceeds 100 tables; source preserved without extraction.')
            for name in names:
                quoted='"'+name.replace('"','""')+'"'
                cursor=conn.execute(f'SELECT * FROM {quoted} LIMIT {MAX_ROWS+1}')
                rows=cursor.fetchall()
                if len(rows)>MAX_ROWS:raise ValueError(f'{name} exceeds 100,000 rows.')
                tables.append(table(name,[[d[0] for d in cursor.description],*[[literal(v) for v in r] for r in rows]],{'format':'sqlite','headerRow':1},notes))
        finally:conn.close()
    return tables,{'notes':notes}


def import_ods(source,options):
    ns={'t':'urn:oasis:names:tc:opendocument:xmlns:table:1.0','x':'urn:oasis:names:tc:opendocument:xmlns:text:1.0','o':'urn:oasis:names:tc:opendocument:xmlns:office:1.0'}
    tables=[];sheets=[];materialized_cells=0
    with zipfile.ZipFile(io.BytesIO(source_bytes(source, allow_empty=True))) as z:
        if sum(i.file_size for i in z.infolist())>100*1024*1024:raise ValueError('Expanded ODS exceeds 100 MiB.')
        data=z.read('content.xml')
        if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('XML declarations unsupported.')
        root=ET.fromstring(data)
        for sheet in root.findall('.//t:table',ns):
            name=sheet.attrib.get('{'+ns['t']+'}name','Sheet');rows=[];formulas=[];merges=[]
            for row in sheet.findall('t:table-row',ns):
                values=[]
                for cell in list(row):
                    count=int(cell.attrib.get('{'+ns['t']+'}number-columns-repeated',1))
                    if count<1 or len(values)+count>MAX_COLS:raise ValueError('Repeated ODS cells exceed column limit.')
                    v='\n'.join(''.join(p.itertext()) for p in cell.findall('x:p',ns))
                    if not v:v=next((cell.attrib.get('{'+ns['o']+'}'+k) for k in ('string-value','date-value','value','boolean-value') if cell.attrib.get('{'+ns['o']+'}'+k) is not None),'')
                    formula=cell.attrib.get('{'+ns['t']+'}formula')
                    if formula:formulas.append({'row':len(rows)+1,'column':len(values)+1,'formula':formula,'cachedValue':v})
                    if cell.attrib.get('{'+ns['t']+'}number-columns-spanned'):merges.append({'row':len(rows)+1,'column':len(values)+1,'attributes':cell.attrib})
                    values.extend([v]*count)
                repeat=int(row.attrib.get('{'+ns['t']+'}number-rows-repeated',1))
                if repeat<1:raise ValueError('ODS row repetition must be positive.')
                # Empty spreadsheet tails are structural, not millions of blank records.
                if not any(values) and repeat>1000:
                    sheets.append({'name':name,'unconvertedBlankTailRows':repeat});continue
                if len(rows)+repeat>MAX_ROWS+1000:raise ValueError('Repeated ODS rows exceed row limit.')
                materialized_cells+=len(values)*repeat
                if materialized_cells>2_000_000:raise ValueError('Expanded ODS exceeds the 2,000,000 cell limit. Use a bounded large-data workflow.')
                rows.extend([values.copy() for _ in range(repeat)])
            sheets.append({'name':name,'formulas':formulas,'mergedCells':merges,'firstRows':rows[:12]})
            try:tables.append(table(name,rows,{'format':'ods','sheet':name,'headerRow':options.get('headersBySheet',{}).get(name,options.get('headerRow',1))},['ODS formulas and cached values recorded separately; formatting retained in original.']))
            except ValueError as exc:sheets[-1]['conversionIssue']=str(exc)
    return tables,{'sheets':sheets,'unsupported':['ODS formatting, annotations and objects remain in the original; annotations are not extracted in this adapter.']}


from extra_imports import archive,geojson,dbf
from document_imports import xml,docx,tar
from pdf_import import pdf
from doc_import import doc
from fixed_width import fixed_width,ERRORS as FIXED_WIDTH_ERRORS
ADAPTERS={'.doc':doc,'.xls':xls,'.pdf':pdf,'.xml':xml,'.docx':docx,'.docm':docx,'.tar':tar,'.tgz':tar,'.gz':tar,'.zip':archive,'.geojson':geojson,'.dbf':dbf,'.csv':import_delimited,'.tsv':import_delimited,'.txt':import_delimited,'.xlsx':import_xlsx,'.json':import_json,'.sqlite':import_sqlite,'.sqlite3':import_sqlite,'.db':import_sqlite,'.gpkg':import_sqlite,'.ods':import_ods}


def ingest(payload):
    source=payload['source'];data=source_bytes(source, allow_empty=True);options=payload.get('options',{});suffix=Path(source.get('name','source')).suffix.lower();adapter=ADAPTERS.get(suffix)
    if suffix=='.fwf' or options.get('textFormat')=='fixed-width':adapter=fixed_width
    tables=[];archaeology={};issue=None
    if options.get('preserveOnly'):
        issue='Intentionally preserved as supporting evidence without tabular conversion.'
    elif adapter:
        try:
            if suffix in ('.xlsx','.ods'):
                from upgrades import safe_archive
                with safe_archive(data):pass
            tables,archaeology=adapter(source,options)
            if suffix=='.xls' and archaeology.get('importReview'):issue='Legacy Excel value extraction is unavailable; the exact original remains preserved.'
            if suffix=='.pdf' and archaeology.get('importReview'):issue='PDF text preview is unavailable; the original remains preserved.'
            if suffix=='.doc' and archaeology.get('importReview'):issue='Legacy Word text preview is unavailable; the exact original remains preserved.'
        except (ValueError,KeyError,IndexError,ET.ParseError,zipfile.BadZipFile,sqlite3.Error,UnicodeError,tarfile.TarError,EOFError,OSError) as exc:
            issue=FIXED_WIDTH_ERRORS.get(str(exc),f'Tabular conversion unavailable: {exc}. Original bytes will still be preserved.')
            if adapter==fixed_width:archaeology={'fixedWidthReview':{'conversionBlocked':True,'reasonCode':str(exc) if str(exc) in FIXED_WIDTH_ERRORS else 'FW_DECODING','reviewedOptions':{k:options.get(k) for k in ['fixedWidths','encoding','headerRow']}}}
    else:issue='No tabular adapter for this format. Preserved as a supporting resource; no scientific context discarded.'
    import mimetypes
    archaeology.setdefault('sourceForensics',{'mimeType':mimetypes.guess_type(source.get('name',''))[0] or 'application/octet-stream','filesystemModifiedAt':source.get('filesystemModifiedAt'),'lineEndings':{'CRLF':data.count(b'\r\n'),'LF':data.count(b'\n')-data.count(b'\r\n'),'CR':data.count(b'\r')-data.count(b'\r\n')},'nullByteCount':data.count(b'\0'),'preservation':'Original bytes retained; extraction may be incomplete.'})
    resource={**source,'bytes':len(data),'sha256':sha(data),'importedAt':datetime.now(timezone.utc).isoformat(),'format':suffix.lstrip('.') or 'unknown','adapterVersion':ADAPTER_VERSION,'role':'data' if tables else 'supporting','archaeology':archaeology,'conversionIssue':issue}
    return {'resource':resource,'tables':tables,'adapterVersion':ADAPTER_VERSION}
