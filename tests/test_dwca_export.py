import copy
import csv
import io
import unittest
import zipfile
from dwca_export import DWC, package, preview, validate_archive


def fixture():
    project = {'id': 'fictional-dwca', 'revision': 4, 'resources': [{'id': 'original', 'sha256': 'a' * 64}], 'tables': [
        {'id': 'occ', 'name': 'Fictional occurrences', 'headers': ['identifier', 'name', 'literal notes'], 'rows': [['001', 'Fictional species', 'line 1\nline 2,"quoted"'], ['1', 'NA', '0']]},
        {'id': 'measure', 'name': 'Fictional measurements', 'headers': ['parent', 'value'], 'rows': [['001', '0'], ['001', 'NA'], ['1', '']]},
        {'id': 'unrelated', 'headers': ['id'], 'rows': [['unjoined']]},
    ], 'audit': [{'original': 'unchanged'}]}
    selection = {'core': {'tableId': 'occ', 'rowType': DWC + 'Occurrence', 'key': 0, 'fields': [{'column': 0, 'term': DWC + 'occurrenceID'}, {'column': 1, 'term': DWC + 'scientificName'}]}, 'extensions': [{'tableId': 'measure', 'rowType': DWC + 'MeasurementOrFact', 'key': 0, 'fields': [{'column': 1, 'term': DWC + 'measurementValue'}]}]}
    return project, selection


def exported(project, selection):
    report = preview(project, selection)
    return package(project, selection, {'fingerprint': report['fingerprint'], 'reviewed': True, 'reviewer': 'Fictional reviewer', 'reason': 'Private synthetic conversion test'})


class DarwinCoreArchiveTests(unittest.TestCase):
    def test_exact_literals_multiline_star_and_separate_preservation(self):
        project, selection = fixture()
        before = copy.deepcopy(project)
        report = preview(project, selection)
        self.assertEqual(report['excludedTableIds'], ['unrelated'])
        self.assertFalse(report['scientificConformance'])
        self.assertEqual(report['tables'][0]['unmappedFields'], 1)
        with exported(project, selection) as artifact:
            result = validate_archive(artifact)
            self.assertEqual([t['rows'] for t in result['tables']], [2, 3])
            self.assertEqual(result['externalConsumer'], 'not verified')
            with zipfile.ZipFile(artifact) as archive:
                for filename, table in [('core.csv', project['tables'][0]), ('extension-1.csv', project['tables'][1])]:
                    rows = list(csv.reader(io.StringIO(archive.read(filename).decode(), newline='')))
                    self.assertEqual(rows, [table['headers'], *table['rows']])
                self.assertNotIn('project.json', archive.namelist())
                self.assertNotIn('unrelated.csv', archive.namelist())
        self.assertEqual(project, before)

    def test_blank_duplicate_or_unmatched_literal_keys_are_refused(self):
        for table_index, row, value in [(0, 1, '001'), (0, 0, ' '), (1, 0, '0001'), (1, 0, '')]:
            with self.subTest(value=value):
                project, selection = fixture()
                project['tables'][table_index]['rows'][row][0] = value
                with self.assertRaisesRegex(ValueError, 'DWCA_LINK'):
                    preview(project, selection)

    def test_explicit_supported_selection_mapping_and_literal_bounds(self):
        for mutation in ('ragged', 'numeric', 'mapping', 'duplicate', 'type', 'oversized'):
            project, selection = fixture()
            if mutation == 'ragged': project['tables'][0]['rows'][0].pop()
            if mutation == 'numeric': project['tables'][0]['rows'][0][0] = 1
            if mutation == 'mapping': selection['core']['fields'][0]['term'] = 'scientificName'
            if mutation == 'duplicate': selection['extensions'][0]['tableId'] = 'occ'
            if mutation == 'type': selection['core']['rowType'] = DWC + 'MeasurementOrFact'
            if mutation == 'oversized': project['tables'][0]['rows'][0][1] = 'a' * 64001
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'DWCA_'):
                preview(project, selection)

    def test_export_requires_review_of_exact_current_data(self):
        project, selection = fixture()
        review = {'reviewed': True, 'fingerprint': preview(project, selection)['fingerprint'], 'reviewer': 'Fictional', 'reason': 'Test'}
        with self.assertRaisesRegex(ValueError, 'DWCA_REVIEW'): package(project, selection, {**review, 'reviewed': False})
        with self.assertRaisesRegex(ValueError, 'DWCA_REVIEW'): package(project, selection, {**review, 'reason': ' '})
        project['tables'][0]['rows'][0][1] = 'Changed after preview'
        with self.assertRaisesRegex(ValueError, 'DWCA_REVIEW'): package(project, selection, review)

    def test_independent_reader_rejects_rewritten_links_and_unsafe_members(self):
        project, selection = fixture()
        with exported(project, selection) as artifact, zipfile.ZipFile(artifact) as archive:
            original = {name: archive.read(name) for name in archive.namelist()}
        for mutation in ('link', 'path', 'entity', 'duplicate'):
            data = dict(original)
            if mutation == 'link': data['extension-1.csv'] = b'parent,value\n0001,0\n'
            if mutation == 'path': data['../evil.csv'] = b'bad'
            if mutation == 'entity': data['meta.xml'] = b'<!DOCTYPE x [<!ENTITY x SYSTEM "file:///private">]><archive/>'
            out = io.BytesIO()
            with zipfile.ZipFile(out, 'w') as archive:
                for name, raw in data.items(): archive.writestr(name, raw)
                if mutation == 'duplicate':
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter('ignore')
                        archive.writestr('core.csv', data['core.csv'])
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'DWCA_ARCHIVE'):
                validate_archive(out)

    def test_pinned_official_schema_failure_is_honest(self):
        project, selection = fixture()
        report = preview(project, selection)['officialDescriptor']
        self.assertEqual(report['status'], 'unavailable')
        self.assertTrue('chrono' in report['reason'] or 'Optional lxml' in report['reason'])
