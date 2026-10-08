"""Reviewed, bounded star-schema export. Never changes scientific declarations."""
import csv
import hashlib
import io
import json
import re
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname
from xml.etree import ElementTree as ET

NS = 'http://rs.tdwg.org/dwc/text/'
DWC = 'http://rs.tdwg.org/dwc/terms/'
ROW_TYPES = {DWC + name for name in ('Occurrence', 'Event', 'Taxon', 'MeasurementOrFact', 'Identification', 'ResourceRelationship')}
CORE_TYPES = {DWC + name for name in ('Occurrence', 'Event', 'Taxon')}
MAX_CELLS = 250_000
MAX_BYTES = 32 * 1024 * 1024
ROOT = Path(__file__).resolve().parent
ET.register_namespace('', NS)


def _json(value):
    try:
        data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError('DWCA_INVALID: Invalid literal project data.') from exc
    if len(data) > MAX_BYTES:
        raise ValueError('DWCA_LIMIT: Project exceeds the 32 MiB preparation bound.')
    return data


def official_schema_check(descriptor):
    """Hash-check pinned originals, prohibit all remote schema/entity resolution."""
    try:
        from lxml import etree
    except ImportError:
        return {'status': 'unavailable', 'reason': 'Optional lxml validator is unavailable.'}
    folder = ROOT / 'vendor-dwca'
    try:
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        by_name = {}
        aliases = {}
        for item in manifest['files']:
            name = item['path']
            if Path(name).name != name:
                raise ValueError('Invalid pinned schema path.')
            path = folder / name
            if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('Pinned schema checksum mismatch: ' + name)
            by_name[name] = path
            for url in (item['url'], item.get('fetchedUrl', ''), str(path.resolve())):
                if url:
                    aliases[url] = path
        aliases['http://rs.gbif.org/schema/xml.xsd'] = by_name['xml.xsd']

        class Offline(etree.Resolver):
            def resolve(self, url, public_id, context):
                path = aliases.get(url)
                if path is None and urlparse(url).scheme == 'file':
                    candidate = Path(url2pathname(urlparse(url).path)).resolve()
                    if candidate.parent == folder.resolve():
                        path = by_name.get(candidate.name)
                if path is None and not re.match(r'^[a-zA-Z]+://', url):
                    candidate = Path(url).resolve()
                    if candidate.parent == folder.resolve():
                        path = by_name.get(candidate.name)
                if path is None:
                    raise ValueError('Unpinned schema reference: ' + url)
                return self.resolve_filename(str(path.resolve()), context)

        parser = etree.XMLParser(no_network=True, resolve_entities=False, load_dtd=False)
        parser.resolvers.add(Offline())
        schema = etree.XMLSchema(etree.parse(str((folder / 'tdwg_dwc_text.xsd').resolve()), parser))
        schema.assertValid(etree.fromstring(descriptor, parser))
        return {'status': 'passed', 'schemaVersion': '0.1', 'scientificConformance': False}
    except (OSError, ValueError, KeyError, etree.Error) as exc:
        return {'status': 'unavailable', 'reason': str(exc)[:1500], 'scientificConformance': False}


def _selection(project, selection):
    if not isinstance(project, dict) or not isinstance(selection, dict):
        raise ValueError('DWCA_INVALID: Select a project, one core and direct extensions.')
    _json(project)
    tables = project.get('tables', [])
    if not isinstance(tables, list) or len(tables) > 100:
        raise ValueError('DWCA_LIMIT: At most 100 ordinary tables can be prepared.')
    ids = [t.get('id') for t in tables if isinstance(t, dict)]
    if len(ids) != len(tables) or len(set(ids)) != len(ids):
        raise ValueError('DWCA_INVALID: Table identifiers must be unique.')
    table_map = {t['id']: t for t in tables}
    core = selection.get('core')
    extensions = selection.get('extensions', [])
    if not isinstance(core, dict) or not isinstance(extensions, list) or len(extensions) > 20:
        raise ValueError('DWCA_INVALID: Exactly one core and at most 20 direct extensions are supported.')
    chosen = [core, *extensions]
    seen = set()
    prepared = []
    cells = 0
    for number, spec in enumerate(chosen):
        if not isinstance(spec, dict):
            raise ValueError('DWCA_INVALID: Invalid table selection.')
        tid = spec.get('tableId')
        if tid not in table_map or tid in seen:
            raise ValueError('DWCA_INVALID: Select each existing table once.')
        seen.add(tid)
        table = table_map[tid]
        headers, rows = table.get('headers'), table.get('rows')
        if not isinstance(headers, list) or not headers or not all(isinstance(x, str) for x in headers) or not isinstance(rows, list):
            raise ValueError('DWCA_INVALID: A selected table has no literal headers or rows.')
        cells += len(headers) * len(rows)
        if cells > MAX_CELLS or len(rows) > 100_000:
            raise ValueError('DWCA_LIMIT: Preparation is bounded to 250,000 cells and 100,000 rows per table.')
        if any(not isinstance(row, list) or len(row) != len(headers) or any(not isinstance(v, str) for v in row) for row in rows):
            raise ValueError('DWCA_INVALID: Ragged or nonliteral cells require explicit review; no padding or coercion was performed.')
        if any(len(v.encode('utf-8')) > 64_000 for row in [headers, *rows] for v in row):
            raise ValueError('DWCA_LIMIT: Individual literal fields are bounded to 64,000 UTF-8 bytes.')
        row_type, key = spec.get('rowType'), spec.get('key')
        if row_type not in (CORE_TYPES if number == 0 else ROW_TYPES):
            raise ValueError('DWCA_INVALID: Select a supported genuine row type explicitly.')
        if type(key) is not int or not 0 <= key < len(headers):
            raise ValueError('DWCA_INVALID: Select the literal core identifier or extension core-link field.')
        fields = spec.get('fields', [])
        if not isinstance(fields, list) or not 1 <= len(fields) <= len(headers):
            raise ValueError('DWCA_INVALID: Review at least one explicit term mapping per selected table.')
        indices, terms = set(), set()
        for field in fields:
            if not isinstance(field, dict):
                raise ValueError('DWCA_INVALID: Invalid field mapping.')
            index, term = field.get('column'), field.get('term')
            if type(index) is not int or not 0 <= index < len(headers) or index in indices:
                raise ValueError('DWCA_INVALID: Field indices must be unique and in range.')
            if not isinstance(term, str) or len(term) > 500 or not re.fullmatch(r'https?://[^\s<>"\x00-\x1f]+', term) or term in terms:
                raise ValueError('DWCA_INVALID: Review a unique absolute HTTP(S) term IRI for each mapped field.')
            indices.add(index)
            terms.add(term)
        values = [row[key] for row in rows]
        if any(not value.strip() for value in values):
            raise ValueError('DWCA_LINK: Blank identifiers or core links cannot be exported.')
        if number == 0:
            if len(set(values)) != len(values):
                raise ValueError('DWCA_LINK: Core identifiers must be unique as exact literal strings.')
            core_ids = set(values)
        elif any(value not in core_ids for value in values):
            raise ValueError('DWCA_LINK: Every extension link must match a literal core identifier; 001 and 1 differ.')
        prepared.append({'table': table, 'spec': spec, 'file': 'core.csv' if number == 0 else f'extension-{number}.csv', 'unmappedFields': len(headers) - len(indices)})
    return prepared, [tid for tid in ids if tid not in seen]


def _descriptor(prepared):
    root = ET.Element('{' + NS + '}archive')
    for number, item in enumerate(prepared):
        spec = item['spec']
        node = ET.SubElement(root, '{' + NS + '}' + ('core' if number == 0 else 'extension'), {'rowType': spec['rowType'], 'encoding': 'UTF-8', 'fieldsTerminatedBy': ',', 'linesTerminatedBy': '\\n', 'fieldsEnclosedBy': '"', 'ignoreHeaderLines': '1'})
        files = ET.SubElement(node, '{' + NS + '}files')
        ET.SubElement(files, '{' + NS + '}location').text = item['file']
        ET.SubElement(node, '{' + NS + '}' + ('id' if number == 0 else 'coreid'), {'index': str(spec['key'])})
        for field in spec['fields']:
            ET.SubElement(node, '{' + NS + '}field', {'index': str(field['column']), 'term': field['term']})
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def preview(project, selection):
    prepared, excluded = _selection(project, selection)
    fingerprint = hashlib.sha256(_json({'project': project, 'selection': selection})).hexdigest()
    return {'kind': 'reviewed-dwca-star-preview', 'fingerprint': fingerprint, 'localStructure': 'passed', 'officialDescriptor': official_schema_check(_descriptor(prepared)), 'scientificConformance': False, 'privacy': 'Private working-data package; no redaction or public-release clearance.', 'tables': [{'tableId': x['table']['id'], 'name': x['table'].get('name', ''), 'rows': len(x['table']['rows']), 'file': x['file'], 'rowType': x['spec']['rowType'], 'mappedFields': len(x['spec']['fields']), 'unmappedFields': x['unmappedFields']} for x in prepared], 'excludedTableIds': excluded, 'limitations': ['Only the explicitly selected one-core/direct-extension star is exported; no joins or flattening.', 'All selected table columns retain literal values. Unmapped columns have no semantic descriptor and may be ignored by consumers.', 'This package does not include source bytes or a recoverable Workbench project. Save a preservation package separately.', 'No scientific, public-release, GBIF-consumer or complete vocabulary conformance is certified.']}


def package(project, selection, review):
    report = preview(project, selection)
    if not isinstance(review, dict) or review.get('reviewed') is not True or review.get('fingerprint') != report['fingerprint']:
        raise ValueError('DWCA_REVIEW: Prepare and acknowledge the current exact selection before export.')
    reviewer, reason = review.get('reviewer'), review.get('reason')
    if not all(isinstance(value, str) and 1 <= len(value.strip()) <= 2000 for value in (reviewer, reason)):
        raise ValueError('DWCA_REVIEW: Record a reviewer and reason for this private conversion.')
    prepared, _ = _selection(project, selection)
    artifact = tempfile.TemporaryFile('w+b')
    try:
        with zipfile.ZipFile(artifact, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('meta.xml', _descriptor(prepared))
            for item in prepared:
                with archive.open(item['file'], 'w') as member:
                    with io.TextIOWrapper(member, encoding='utf-8', newline='') as text:
                        writer = csv.writer(text, lineterminator='\n')
                        writer.writerow(item['table']['headers'])
                        writer.writerows(item['table']['rows'])
            provenance = {'report': report, 'selection': selection, 'projectId': project.get('id'), 'projectRevision': project.get('revision'), 'reviewer': reviewer.strip(), 'reason': reason.strip(), 'sourceHashes': [{'resourceId': r.get('id'), 'sha256': r.get('sha256')} for r in project.get('resources', [])], 'projectChanged': False}
            archive.writestr('workbench-conversion.json', _json(provenance))
            archive.writestr('README.txt', '\n'.join([report['privacy'], *report['limitations']]) + '\n')
        artifact.seek(0)
        validate_archive(artifact)
        return artifact
    except BaseException:
        artifact.close()
        raise


def validate_archive(artifact):
    """Independently read bounded exported bytes, not their recorded preview report."""
    artifact.seek(0)
    try:
        with zipfile.ZipFile(artifact) as archive:
            members = archive.infolist()
            names = [m.filename for m in members]
            if len(names) > 24 or len(set(names)) != len(names) or 'meta.xml' not in names or sum(m.file_size for m in members) > MAX_BYTES:
                raise ValueError('DWCA_ARCHIVE: Invalid member inventory or size.')
            if any(not re.fullmatch(r'(meta\.xml|core\.csv|extension-[1-9][0-9]?\.csv|workbench-conversion\.json|README\.txt)', name) for name in names):
                raise ValueError('DWCA_ARCHIVE: Unsupported member path.')
            meta = archive.read('meta.xml')
            if len(meta) > 256_000 or b'<!DOCTYPE' in meta.upper() or b'<!ENTITY' in meta.upper():
                raise ValueError('DWCA_ARCHIVE: Unsafe or oversized descriptor.')
            root = ET.fromstring(meta)
            children = list(root)
            if root.tag != '{' + NS + '}archive' or not children or children[0].tag != '{' + NS + '}core' or any(n.tag != '{' + NS + '}extension' for n in children[1:]):
                raise ValueError('DWCA_ARCHIVE: Exactly one core followed by direct extensions is required.')
            used, cells, counts = set(), 0, []
            for number, node in enumerate(children):
                if any(node.get(key) != value for key, value in {'encoding': 'UTF-8', 'fieldsTerminatedBy': ',', 'fieldsEnclosedBy': '"', 'linesTerminatedBy': '\\n', 'ignoreHeaderLines': '1'}.items()):
                    raise ValueError('DWCA_ARCHIVE: Unsupported CSV dialect.')
                if node.get('rowType') not in (CORE_TYPES if number == 0 else ROW_TYPES):
                    raise ValueError('DWCA_ARCHIVE: Unsupported row type.')
                locations = node.findall('{' + NS + '}files/{' + NS + '}location')
                if len(locations) != 1 or locations[0].text not in names or locations[0].text in used or not locations[0].text.endswith('.csv'):
                    raise ValueError('DWCA_ARCHIVE: Missing, duplicate or unsupported data location.')
                name = locations[0].text
                used.add(name)
                with archive.open(name) as raw, io.TextIOWrapper(raw, encoding='utf-8', newline='') as text:
                    reader = csv.reader(text, strict=True)
                    headers = next(reader, None)
                    if not headers:
                        raise ValueError('DWCA_ARCHIVE: Data header is missing.')
                    links = node.findall('{' + NS + '}' + ('id' if number == 0 else 'coreid'))
                    if len(links) != 1:
                        raise ValueError('DWCA_ARCHIVE: Identifier descriptor is missing.')
                    key = int(links[0].get('index', '-1'))
                    fields = node.findall('{' + NS + '}field')
                    indices, terms = set(), set()
                    if not fields or not 0 <= key < len(headers):
                        raise ValueError('DWCA_ARCHIVE: Invalid identifier or mappings.')
                    for field in fields:
                        index, term = int(field.get('index', '-1')), field.get('term', '')
                        if not 0 <= index < len(headers) or index in indices or term in terms or not re.fullmatch(r'https?://[^\s<>"\x00-\x1f]+', term):
                            raise ValueError('DWCA_ARCHIVE: Invalid mapping index or IRI.')
                        indices.add(index)
                        terms.add(term)
                    identifiers = set() if number == 0 else None
                    count = 0
                    for row in reader:
                        count += 1
                        cells += len(row)
                        if count > 100_000 or cells > MAX_CELLS or len(row) != len(headers) or not row[key].strip():
                            raise ValueError('DWCA_ARCHIVE: Invalid literal record or data bound.')
                        if number == 0:
                            if row[key] in identifiers:
                                raise ValueError('DWCA_ARCHIVE: Duplicate literal core identifier.')
                            identifiers.add(row[key])
                        elif row[key] not in core_ids:
                            raise ValueError('DWCA_ARCHIVE: Unmatched literal core link.')
                    if number == 0:
                        core_ids = identifiers
                    counts.append({'file': name, 'rows': count})
            if used != {name for name in names if name.endswith('.csv')}:
                raise ValueError('DWCA_ARCHIVE: Undescribed data tables.')
            return {'localStructure': 'passed', 'tables': counts, 'officialDescriptor': official_schema_check(meta), 'scientificConformance': False, 'externalConsumer': 'not verified'}
    except (zipfile.BadZipFile, csv.Error, UnicodeError, ET.ParseError, KeyError, RuntimeError) as exc:
        raise ValueError('DWCA_ARCHIVE: Malformed or unreadable archive.') from exc
    finally:
        artifact.seek(0)
