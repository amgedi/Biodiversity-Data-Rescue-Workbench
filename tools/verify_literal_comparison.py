"""Independently recompute a private literal comparison against a saved project.

Reads both inputs without modifying them. This checks reproducibility, not identity,
scientific equivalence, authenticity, or current independent archive availability.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path

LIMITS = dict(rowsPerTable=100000, fields=100, keyPairs=5, cells=2000000,
              keyCodeUnits=10000000, reportBytes=20*1024*1024)
MATCHING = 'exact ordered literal strings; only empty key components are unlinked'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def js_json(value):
    text = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    # JSON.stringify escapes unpaired UTF-16 surrogates, retaining other Unicode.
    return ''.join('\\u%04x' % ord(c) if 0xD800 <= ord(c) <= 0xDFFF else c for c in text)


def integer(value):
    return type(value) is int


def validate_table(table):
    headers, rows = table.get('headers'), table.get('rows')
    require(isinstance(headers, list) and 1 <= len(headers) <= 250 and
            all(isinstance(h, str) and len(h.encode('utf-16-le', 'surrogatepass'))//2 <= 1000 for h in headers), 'Invalid headers')
    require(isinstance(rows, list) and len(rows) <= LIMITS['rowsPerTable'], 'Invalid record count')
    require(all(isinstance(row, list) and len(row) == len(headers) and all(isinstance(v, str) for v in row) for row in rows), 'Invalid record shape')
    origins, original = table.get('rowOrigins'), table.get('originalTable')
    require(original is None or isinstance(original.get('rows'), list), 'Invalid original table')
    require(origins is None or isinstance(origins, list) and len(origins) == len(rows) and
            all(integer(n) and n >= 0 and (original is None or n < len(original['rows'])) for n in origins), 'Invalid original record provenance')


def compare(left, right, recipe):
    for table in (left, right):
        validate_table(table)
    for name, limit in [('keys', LIMITS['keyPairs']), ('fields', LIMITS['fields'])]:
        pairs = recipe.get(name)
        require(isinstance(pairs, list) and 1 <= len(pairs) <= limit, 'Invalid pair count')
        require(all(isinstance(pair, list) and len(pair) == 2 and all(integer(n) for n in pair)
                    and 0 <= pair[0] < len(left['headers']) and 0 <= pair[1] < len(right['headers']) for pair in pairs), 'Invalid pair selection')
        require(len(set(map(tuple, pairs))) == len(pairs), 'Repeated pair selection')
    require((len(left['rows']) + len(right['rows'])) * (len(recipe['keys']) + len(recipe['fields'])) <= LIMITS['cells'], 'Comparison work limit')
    budget = LIMITS['keyCodeUnits']
    indexes = []
    for side, table in enumerate((left, right)):
        groups, keys = {}, []
        for index, row in enumerate(table['rows']):
            values = tuple(row[pair[side]] for pair in recipe['keys'])
            budget -= sum(len(v.encode('utf-16-le', 'surrogatepass'))//2 for v in values)
            require(budget >= 0, 'Comparison key limit')
            key = None if '' in values else values
            keys.append(key)
            if key is not None:
                groups.setdefault(key, []).append(index)
        indexes.append((groups, keys))
    (a, ak), (b, bk) = indexes
    counts = dict.fromkeys(['equal', 'different', 'leftOnly', 'rightOnly', 'leftMissingKey', 'rightMissingKey', 'ambiguous'], 0)
    records, consumed = [], set()

    def origin(table, index):
        return table['rowOrigins'][index] + 1 if index is not None and table.get('originalTable') and isinstance(table.get('rowOrigins'), list) else None

    def add(status, li=None, ri=None, lc=0, rc=0, changed=None):
        counts[status] += 1
        records.append(dict(status=status, leftRecord=None if li is None else li+1, rightRecord=None if ri is None else ri+1,
                            leftOriginalRecord=origin(left, li), rightOriginalRecord=origin(right, ri),
                            leftKeyMultiplicity=lc, rightKeyMultiplicity=rc, changedFields=changed or []))

    for li, key in enumerate(ak):
        if key is None:
            add('leftMissingKey', li)
        elif key not in b:
            add('leftOnly', li, lc=len(a[key]))
        elif len(a[key]) != 1 or len(b[key]) != 1:
            add('ambiguous', li, lc=len(a[key]), rc=len(b[key]))
        else:
            ri = b[key][0]
            changed = [i for i, (lc, rc) in enumerate(recipe['fields']) if left['rows'][li][lc] != right['rows'][ri][rc]]
            consumed.add(ri)
            add('different' if changed else 'equal', li, ri, 1, 1, changed)
    for ri, key in enumerate(bk):
        if ri in consumed:
            continue
        if key is None:
            add('rightMissingKey', ri=ri)
        else:
            add('ambiguous' if key in a else 'rightOnly', ri=ri, lc=len(a.get(key, [])), rc=len(b[key]))
    return dict(comparisonVersion=1, matching=MATCHING, limits=LIMITS, counts=counts,
                leftRecords=len(left['rows']), rightRecords=len(right['rows']),
                leftDuplicateKeyGroups=sum(len(g) > 1 for g in a.values()),
                rightDuplicateKeyGroups=sum(len(g) > 1 for g in b.values()), records=records)


def verify(project, report):
    require(report.get('reportVersion') == 1 and project.get('id') == report.get('projectId'), 'Wrong project or report version')
    require(integer(report.get('projectRevision')) and report['projectRevision'] >= 0, 'Invalid historical revision')
    require(report.get('scientificEquivalenceAsserted') is False and report.get('sourceOrWorkingDataChanged') is False, 'Invalid comparison claims')
    review = report.get('review', {})
    require(review.get('confirmedLiteralPairing') is True and isinstance(review.get('reviewer'), str) and len(review['reviewer']) <= 200
            and isinstance(review.get('reason'), str) and 0 < len(review['reason'].strip()) <= 4000, 'Missing reviewed pairing')
    tables = []
    for side, name in enumerate(('left', 'right')):
        descriptor = report[name]
        found = [t for t in project.get('tables', []) if t.get('id') == descriptor.get('tableId')]
        require(len(found) == 1, 'Missing or ambiguous table')
        table = found[0]
        validate_table(table)
        fingerprint = hashlib.sha256(js_json([table['headers'], table['rows'], table.get('rowOrigins')]).encode('utf-8')).hexdigest()
        require(descriptor.get('workingFingerprint') == fingerprint, 'Working table fingerprint mismatch')
        for key in ('name', 'resourceId', 'headers', 'rowOrigins'):
            require(descriptor.get(key) == table.get(key), 'Table context mismatch: '+key)
        indices = list(dict.fromkeys(pair[side] for pair in report['recipe']['keys'] + report['recipe']['fields']))
        columns = table.get('columns', [])
        expected = [dict(index=i, definition=columns[i] if 0 <= i < len(columns) else None) for i in indices]
        require(descriptor.get('selectedDefinitions') == expected, 'Selected definitions mismatch')
        tables.append(table)
    require(tables[0]['id'] != tables[1]['id'], 'Same table on both sides')
    source_ids = {t['resourceId'] for t in tables}
    sources = report.get('sources', [])
    require(len(sources) == len(source_ids) and {s['id'] for s in sources} == source_ids, 'Source inventory mismatch')
    checks = report.get('integrity', [])
    require(len(checks) == len(source_ids) and {c['resourceId'] for c in checks} == source_ids, 'Integrity inventory mismatch')
    for source in sources:
        found = [s for s in project.get('resources', []) if s.get('id') == source['id']]
        require(len(found) == 1, 'Source not uniquely available')
        original = found[0]
        require(all(source.get(k) == original.get(k) for k in ('id', 'name', 'sha256', 'bytes')), 'Source context mismatch')
        raw = base64.b64decode(original['base64'], validate=True)
        require(hashlib.sha256(raw).hexdigest() == source['sha256'] and len(raw) == source['bytes'], 'Original source bytes mismatch')
        check = next(c for c in checks if c['resourceId'] == source['id'])
        require(check.get('expected') == source['sha256'] and check.get('expectedBytes') == source['bytes'] and
                all(check.get(k) is True for k in ('backupMatches', 'diskMatches', 'backupByteLengthMatches', 'diskByteLengthMatches')), 'Invalid recorded integrity check')
    require(report['result'] == compare(*tables, report['recipe']), 'Recomputed complete record outcomes differ')
    return dict(verified=True, tables=2, records=len(report['result']['records']), scientificEquivalenceAsserted=False,
                independentArchiveRechecked=False)


def load(path, cap):
    require(path.stat().st_size <= cap, 'Input exceeds verifier size limit')
    return json.loads(path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    try:
        result = verify(load(args.project, 256*1024*1024), load(args.report, LIMITS['reportBytes']))
    except (ValueError, KeyError, TypeError, IndexError, OSError) as error:
        parser.exit(1, 'Verification failed: '+str(error)+'\n')
    print(json.dumps(result, indent=2))
