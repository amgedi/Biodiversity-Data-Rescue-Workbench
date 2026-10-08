import base64
import io
import json
import unittest
import zipfile
from rescue import inspect, export_project, sha


def payload(data, name='source.csv', **options):
    return {'source': {'name': name, 'base64': base64.b64encode(data).decode()}, 'options': options}


class RescueTests(unittest.TestCase):
    def test_quotes_multiline_and_ragged_rows_preserved(self):
        data = b'id,notes\r\n001,"bird, calling\nnear stream"\r\n002,seen,extra\r\n003\r\n'
        result = inspect(payload(data, delimiter=','))
        self.assertEqual(result['headers'], ['id', 'notes', 'column_3'])
        self.assertEqual(result['rows'][0], ['001', 'bird, calling\nnear stream', ''])
        self.assertEqual(result['rows'][1], ['002', 'seen', 'extra'])
        self.assertEqual(result['rowWidths'], [2, 3, 1])
        self.assertEqual(result['sha256'], sha(data))

    def test_encoding_and_header_overrides(self):
        result = inspect(payload('field notes\nsite;count\nforêt;0\n'.encode('cp1252'), encoding='cp1252', delimiter=';', headerRow=2))
        self.assertEqual(result['rows'], [['forêt', '0']])
        result = inspect(payload('id\tname\n01\tÉlan'.encode('utf-16')))
        self.assertEqual(result['parsing']['encoding'], 'utf-16')
        self.assertEqual(result['rows'][0], ['01', 'Élan'])

    def test_headers_unique_and_original_retained(self):
        result = inspect(payload(b'a,a,,a_2\n1,2,3,4'))
        self.assertEqual(len(set(result['headers'])), 4)
        self.assertEqual(result['originalHeaders'], ['a', 'a', '', 'a_2'])

    def test_reject_empty_bad_decode_and_quotes(self):
        for p in [payload(b''), payload(b'\xff', encoding='utf-8'), payload(b'a,b\n"unterminated', delimiter=','), payload(b'a,b', headerRow=3), payload(b'fake', name='a.xls')]:
            with self.assertRaises(ValueError):
                inspect(p)

    def test_xlsx_sheets_sparse_cells_and_formula_cache(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as z:
            z.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Observations" r:id="rId1"/><sheet name="Notes" r:id="rId2"/></sheets></workbook>')
            z.writestr('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Target="worksheets/sheet2.xml"/></Relationships>')
            z.writestr('xl/worksheets/sheet1.xml', '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>id</t></is></c><c r="C1" t="inlineStr"><is><t>count</t></is></c></row><row r="2"><c r="A2" t="inlineStr"><is><t>001</t></is></c><c r="C2"><f>1+1</f><v>2</v></c></row></sheetData></worksheet>')
            z.writestr('xl/worksheets/sheet2.xml', '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c t="inlineStr"><is><t>notes</t></is></c></row><row r="2"><c t="inlineStr"><is><t>context</t></is></c></row></sheetData></worksheet>')
        p = payload(stream.getvalue(), 'workbook.xlsx')
        result = inspect(p)
        self.assertEqual(result['rows'], [['001', '', '2']])
        self.assertTrue(any('formula' in note for note in result['notes']))
        p['options']['sheet'] = 'Notes'
        self.assertEqual(inspect(p)['rows'], [['context']])

    def test_export_integrity_literal_values_and_reopenable_backup(self):
        data = b'id,count\n001,0\n002,=1+1\n'
        p = payload(data)
        result = inspect(p)
        project = {'version': 1, 'id': 'test', 'source': {**p['source'], 'sha256': sha(data)}, 'headers': result['headers'], 'rows': result['rows'], 'metadata': {'title': 'Woodland'}, 'columns': [{}, {}], 'audit': [{'action': 'import'}]}
        content = export_project(project)
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            self.assertEqual(z.read('original/source.csv'), data)
            self.assertIn(b'001,0\n002,=1+1', z.read('cleaned.csv'))
            for line in z.read('checksums.sha256').decode().splitlines():
                digest, path = line.split('  ', 1)
                self.assertEqual(sha(z.read(path)), digest)
            self.assertEqual(json.loads(z.read('project.biorescue.json')), project)
            descriptor = json.loads(z.read('datapackage.json'))
            self.assertEqual(descriptor['resources'][0]['schema']['fields'][0]['type'], 'string')
        project['source']['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            export_project(project)


if __name__ == '__main__':
    unittest.main()
