"""Loss-conscious table ingestion and open-format rescue packaging (stdlib only)."""
import base64
import csv
import hashlib
import io
import json
import posixpath
import re
import zipfile
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

MAX_FILE = 20 * 1024 * 1024
MAX_ROWS = 100_000
MAX_COLS = 250
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_bytes(source, allow_empty=False):
    try:
        data = base64.b64decode(source['base64'], validate=True)
    except (KeyError, ValueError) as exc:
        raise ValueError('Invalid source bytes in project.') from exc
    if len(data) > MAX_FILE:
        raise ValueError('Source exceeds the 20 MiB limit.')
    if not data and not allow_empty:
        raise ValueError('The source file is empty.')
    return data


def shape(rows, header_row):
    if not rows or not 1 <= header_row <= len(rows):
        raise ValueError('Choose a header row within the table.')
    rows = rows[header_row - 1:]
    if len(rows) - 1 > MAX_ROWS:
        raise ValueError('The table exceeds 100,000 data rows.')
    width = max(map(len, rows))
    if width > MAX_COLS:
        raise ValueError('The table exceeds 250 columns.')
    raw_headers = rows[0]
    headers, used = [], set()
    for i in range(width):
        name = raw_headers[i] if i < len(raw_headers) else ''
        name = name or f'column_{i + 1}'
        candidate, n = name, 2
        while candidate in used:
            candidate = f'{name}_{n}'
            n += 1
        used.add(candidate)
        headers.append(candidate)
    widths = [len(r) for r in rows[1:]]
    return headers, [r + [''] * (width - len(r)) for r in rows[1:]], widths, raw_headers


def text_table(data, options):
    allowed = {'utf-8', 'utf-8-sig', 'utf-16', 'cp1252', 'latin-1'}
    encoding = options.get('encoding', 'auto')
    notes = []
    if encoding == 'auto':
        if data.startswith((b'\xff\xfe', b'\xfe\xff')):
            encoding = 'utf-16'
        elif data.startswith(b'\xef\xbb\xbf'):
            encoding = 'utf-8-sig'
        else:
            try:
                data.decode('utf-8')
                encoding = 'utf-8'
            except UnicodeDecodeError:
                encoding = 'cp1252'
                notes.append('UTF-8 decoding failed. Windows-1252 was selected; verify accented characters in the preview.')
    if encoding not in allowed:
        raise ValueError('Unsupported encoding.')
    try:
        decoded = data.decode(encoding, errors='strict')
    except UnicodeError as exc:
        raise ValueError('Decoding failed. Choose another encoding; no bytes were discarded.') from exc
    if '\x00' in decoded:
        raise ValueError('NUL bytes detected. This may be UTF-16 without a BOM; choose UTF-16 or convert a copy.')
    delimiter = options.get('delimiter', 'auto')
    if delimiter == 'auto':
        try:
            delimiter = csv.Sniffer().sniff(decoded[:65536], delimiters=',\t;|').delimiter
        except csv.Error:
            delimiter = '\t' if '\t' in decoded.splitlines()[0] else ','
            notes.append('Delimiter detection was uncertain. Confirm the delimiter before importing.')
    if delimiter not in (',', '\t', ';', '|'):
        raise ValueError('Unsupported delimiter.')
    try:
        rows = []
        for row in csv.reader(io.StringIO(decoded, newline=''), delimiter=delimiter, strict=True):
            rows.append(row)
            if len(rows) > MAX_ROWS + 1000 or len(row) > MAX_COLS:
                raise ValueError('Table exceeds the row or column limit.')
    except csv.Error as exc:
        raise ValueError(f'Invalid quoted delimited text: {exc}') from exc
    return rows, {'encoding': encoding, 'delimiter': delimiter, 'format': 'delimited'}, notes


def xlsx_table(data, options):
    notes = ['XLSX reads stored values only. Formulas are not recalculated; numeric Excel dates need explicit review.']
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError('This is not a readable XLSX workbook.') from exc
    with archive as z:
        if sum(i.file_size for i in z.infolist()) > 100 * 1024 * 1024:
            raise ValueError('Expanded workbook exceeds 100 MiB.')
        def xml(path):
            payload = z.read(path)
            if b'<!DOCTYPE' in payload.upper() or b'<!ENTITY' in payload.upper():
                raise ValueError('Workbook XML declarations are unsupported.')
            return ET.fromstring(payload)
        workbook = xml('xl/workbook.xml')
        relations = {r.attrib['Id']: r.attrib['Target'] for r in xml('xl/_rels/workbook.xml.rels') if r.attrib.get('TargetMode') != 'External'}
        sheets = [(s.attrib['name'], s.attrib[f'{{{REL}}}id']) for s in workbook.findall('s:sheets/s:sheet', NS)]
        if not sheets:
            raise ValueError('Workbook contains no worksheets.')
        selected = options.get('sheet') or sheets[0][0]
        rid = next((rid for name, rid in sheets if name == selected), None)
        if rid not in relations:
            raise ValueError('Selected worksheet was not found.')
        path = relations[rid]
        path = path.lstrip('/') if path.startswith('/') else posixpath.normpath('xl/' + path)
        if not path.startswith('xl/'):
            raise ValueError('Invalid worksheet path.')
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            # Only text nodes, excluding phonetic annotations.
            shared = [''.join(t.text or '' for t in si.findall('.//s:t', NS)) for si in xml('xl/sharedStrings.xml').findall('s:si', NS)]
        rows, formula_count, styled_numbers = [], 0, 0
        for row in xml(path).findall('s:sheetData/s:row', NS):
            row_number = int(row.attrib.get('r', len(rows) + 1))
            if row_number > MAX_ROWS + 1000:
                raise ValueError('Worksheet exceeds row limit.')
            while len(rows) < row_number - 1:
                rows.append([])
            values = []
            for cell in row.findall('s:c', NS):
                reference = cell.attrib.get('r', '')
                letters = re.match(r'([A-Z]+)', reference)
                column = 0
                if letters:
                    for letter in letters[1]:
                        column = column * 26 + ord(letter) - 64
                    column -= 1
                else:
                    column = len(values)
                if column >= MAX_COLS:
                    raise ValueError('Worksheet exceeds 250 columns.')
                while len(values) <= column:
                    values.append('')
                value = cell.findtext('s:v', default='', namespaces=NS)
                kind = cell.attrib.get('t')
                if kind == 's':
                    value = shared[int(value)] if value else ''
                elif kind == 'inlineStr':
                    value = ''.join(t.text or '' for t in cell.findall('.//s:t', NS))
                elif kind == 'b':
                    value = 'TRUE' if value == '1' else 'FALSE'
                if cell.find('s:f', NS) is not None:
                    formula_count += 1
                if cell.attrib.get('s') and kind in (None, 'n') and value:
                    styled_numbers += 1
                values[column] = value
            rows.append(values)
        if formula_count:
            notes.append(f'{formula_count} formula cells imported as cached values; absent caches become empty cells.')
        if styled_numbers:
            notes.append(f'{styled_numbers} styled numeric cells may include Excel date serials. Values were preserved literally.')
    return rows, {'format': 'xlsx', 'encoding': 'XLSX XML', 'delimiter': None, 'sheet': selected, 'sheets': [n for n, _ in sheets]}, notes


def inspect(payload):
    source = payload['source']
    data = source_bytes(source)
    options = payload.get('options', {})
    name = source.get('name', 'source.csv')
    if name.lower().endswith('.xls'):
        raise ValueError('Legacy XLS is unsupported. Save a copy as XLSX or CSV first.')
    try:
        rows, parsing, notes = xlsx_table(data, options) if name.lower().endswith('.xlsx') else text_table(data, options)
        header = int(options.get('headerRow', 1))
        headers, values, widths, original_headers = shape(rows, header)
    except (KeyError, IndexError, ET.ParseError, zipfile.BadZipFile) as exc:
        raise ValueError('The workbook structure is damaged or unsupported.') from exc
    parsing['headerRow'] = header
    if headers != original_headers:
        notes.append('Blank, duplicate, or absent column names were given unique working names. Original headers are recorded.')
    return {'headers': headers, 'rows': values, 'rowWidths': widths, 'originalHeaders': original_headers, 'parsing': parsing, 'notes': notes, 'sha256': sha(data), 'bytes': len(data)}


def csv_bytes(headers, rows):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(headers)
    writer.writerows(rows)
    return stream.getvalue().encode('utf-8')


def export_project(project):
    if project.get('version') != 1:
        raise ValueError('Unsupported project version.')
    data = source_bytes(project['source'])
    if sha(data) != project['source'].get('sha256'):
        raise ValueError('Original source checksum mismatch. Export stopped.')
    headers, rows = project['headers'], project['rows']
    if not headers or len(headers) > MAX_COLS or len(rows) > MAX_ROWS:
        raise ValueError('Invalid table dimensions.')
    if any(len(r) != len(headers) or any(not isinstance(v, str) for v in r) for r in rows):
        raise ValueError('Working table must contain rectangular string values.')
    if len(set(headers)) != len(headers) or any(not isinstance(h, str) or not h.strip() for h in headers):
        raise ValueError('Column names must be nonempty and unique.')
    metadata = project.get('metadata', {})
    columns = project.get('columns', [])
    fields = []
    for i, header in enumerate(headers):
        column = columns[i] if i < len(columns) else {}
        fields.append({'name': header, 'type': 'string', 'description': column.get('description', ''), 'unit': column.get('unit', ''), 'biodiversity:term': column.get('term', ''), 'biodiversity:missingToken': column.get('missingToken', '')})
    filename = re.sub(r'[^A-Za-z0-9._-]', '_', project['source'].get('name', 'source'))[:120] or 'source'
    source_path = 'original/' + filename
    descriptor = {'profile': 'tabular-data-package', 'name': 'biodiversity-rescue', 'title': metadata.get('title') or 'Rescued ecological dataset', 'description': metadata.get('description', ''), 'resources': [{'name': 'cleaned', 'path': 'cleaned.csv', 'profile': 'tabular-data-resource', 'format': 'csv', 'encoding': 'utf-8', 'dialect': {'delimiter': ',', 'lineTerminator': '\n'}, 'schema': {'fields': fields, 'missingValues': ['']}}]}
    if metadata.get('license'):
        descriptor['biodiversity:licenseStatement'] = metadata['license']
    details = {'application': 'Biodiversity Data Rescue Workbench', 'version': 1, 'projectId': project.get('id'), 'createdAt': project.get('createdAt'), 'exportedAt': datetime.now(timezone.utc).isoformat(), 'dataset': metadata, 'columns': columns, 'source': {k: v for k, v in project['source'].items() if k != 'base64'}, 'parsing': project.get('parsing'), 'originalHeaders': project.get('originalHeaders'), 'importNotes': project.get('notes', []), 'rowCount': len(rows), 'columnCount': len(headers), 'valuePolicy': 'All working values exported as literal strings; no implicit scientific interpretation.'}
    def json_bytes(value):
        return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    files = {source_path: data, 'cleaned.csv': csv_bytes(headers, rows), 'metadata.json': json_bytes(details), 'datapackage.json': json_bytes(descriptor), 'audit.json': json_bytes(project.get('audit', [])), 'quality-report.json': json_bytes({'advisory': True, 'issues': project.get('qualityReview', []), 'columnProfiles': project.get('columnProfiles', []), 'note': 'Rule-based suggestions, not scientific validation.'}), 'project.biorescue.json': json_bytes(project)}
    files['README.txt'] = ('''BIODIVERSITY DATA RESCUE PACKAGE

original/: exact imported bytes. Do not edit this source.
cleaned.csv: UTF-8 comma-delimited working table; all values are strings.
metadata.json: dataset context, column definitions, parsing choices and source hash.
datapackage.json: tabular data package descriptor, with biodiversity extensions.
audit.json: ordered timestamped actions with before/after snapshots and reasons.
quality-report.json: unresolved rule-based flags and column profiles at export.
project.biorescue.json: portable project, reopen in the Workbench.
checksums.sha256: SHA-256 of each other file in this package.

REVIEW BEFORE SHARING: exact coordinates and original workbook content can be sensitive.
Metadata and term mappings are user assertions, not validated scientific claims.
Blank values remain blank; zero remains zero. No absence or effort was inferred.

SPREADSHEET SAFETY: CSV cells beginning with =, +, -, or @ can be interpreted as
formulas by spreadsheet software. Import all columns explicitly as TEXT; avoid
double-clicking the CSV. Literal values are preserved for reproducibility.
Excel formula caches and date serials require manual review.
''').encode('utf-8')
    files['checksums.sha256'] = ''.join(f'{sha(content)}  {path}\n' for path, content in files.items()).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return output.getvalue()
