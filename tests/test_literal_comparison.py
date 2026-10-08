import base64
import copy
import hashlib
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('literal_verifier', Path(__file__).resolve().parents[1]/'tools/verify_literal_comparison.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


class LiteralComparisonVerification(unittest.TestCase):
    def fixture(self):
        tables, sources = [], []
        for name, values in [('left', [['001', 'frog'], ['0', '0'], ['NA', 'unknown'], ['A', 'one'], ['A', 'two'], ['', 'empty']]),
                             ('right', [['0', '0'], ['001', 'frog'], ['NA', 'UNKNOWN'], ['A', 'one'], ['', 'empty'], ['B', 'only']])]:
            raw = name.encode()
            sources.append(dict(id=name, name=name+'.csv', sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), base64=base64.b64encode(raw).decode()))
            tables.append(dict(id=name, name=name, resourceId=name, headers=['id', 'value'], rows=values,
                               columns=[{'status': 'Unknown'}, {'status': 'Inferred'}], rowOrigins=list(range(len(values))), originalTable={'rows': copy.deepcopy(values)}))
        project = dict(id='fictional', revision=9, resources=sources, tables=tables)
        recipe = dict(keys=[[0, 0]], fields=[[1, 1]])
        report = dict(reportVersion=1, projectId='fictional', projectRevision=9, review=dict(reviewer='Fictional custodian', reason='Literal pairing only', confirmedLiteralPairing=True),
                      recipe=recipe, scientificEquivalenceAsserted=False, sourceOrWorkingDataChanged=False,
                      sources=[{k: s[k] for k in ('id', 'name', 'sha256', 'bytes')} for s in sources],
                      integrity=[dict(resourceId=s['id'], expected=s['sha256'], expectedBytes=s['bytes'], backupMatches=True, diskMatches=True, backupByteLengthMatches=True, diskByteLengthMatches=True) for s in sources],
                      result=v.compare(*tables, recipe))
        for name, table in zip(('left', 'right'), tables):
            report[name] = dict(tableId=table['id'], name=table['name'], resourceId=table['resourceId'], headers=table['headers'], rowOrigins=table['rowOrigins'],
                                selectedDefinitions=[dict(index=i, definition=table['columns'][i]) for i in (0, 1)],
                                workingFingerprint=hashlib.sha256(v.js_json([table['headers'], table['rows'], table['rowOrigins']]).encode()).hexdigest())
        return project, copy.deepcopy(report)

    def test_complete_report_recomputed_and_revision_change_does_not_hide_identical_snapshot(self):
        project, report = self.fixture()
        self.assertTrue(v.verify(project, report)['verified'])
        project['revision'] += 1
        self.assertTrue(v.verify(project, report)['verified'])
        self.assertEqual(report['result']['counts']['ambiguous'], 3)
        self.assertFalse(v.verify(project, report)['independentArchiveRechecked'])

    def test_source_definitions_fingerprints_and_record_outcomes_reject_tampering(self):
        for mutation in ('source', 'definition', 'fingerprint', 'outcome', 'count', 'origin', 'integrity', 'identity'):
            with self.subTest(mutation=mutation):
                project, report = self.fixture()
                if mutation == 'source': project['resources'][0]['base64'] = base64.b64encode(b'fake').decode()
                if mutation == 'definition': project['tables'][0]['columns'][1]['status'] = 'Confirmed'
                if mutation == 'fingerprint': report['left']['workingFingerprint'] = '0'*64
                if mutation == 'outcome': report['result']['records'][0]['rightRecord'] = 1
                if mutation == 'count': report['result']['counts']['equal'] += 1
                if mutation == 'origin': report['result']['records'][0]['leftOriginalRecord'] = 2
                if mutation == 'integrity': report['integrity'][0]['diskMatches'] = False
                if mutation == 'identity': report['projectId'] = 'another'
                with self.assertRaises(ValueError): v.verify(project, report)

    def test_unicode_literal_composite_matching_and_invalid_selection(self):
        project, report = self.fixture()
        for table in project['tables']:
            table['rows'] = [['a|b', 'c'], ['a', 'b|c'], ['𓆏', ' frog '], ['', '0']]
            table['originalTable']['rows'] = copy.deepcopy(table['rows'])
            table['rowOrigins'] = [0, 1, 2, 3]
        result = v.compare(*project['tables'], dict(keys=[[0, 0], [1, 1]], fields=[[1, 1]]))
        self.assertEqual(result['counts']['equal'], 3)
        self.assertEqual(result['counts']['leftMissingKey'], 1)
        with self.assertRaises(ValueError): v.compare(*project['tables'], dict(keys=[[True, 0]], fields=[[1, 1]]))
        self.assertEqual(v.js_json(['𓆏', '\ud800']), '["𓆏","\\ud800"]')


if __name__ == '__main__':
    unittest.main()
