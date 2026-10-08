import base64
import io
import json
import tempfile
import unittest
import zipfile
import sqlite3
from pathlib import Path
from importers import ingest, excel_archaeology
from storage import Store
from exporters import export_v2,structure_checks
from rescue import sha

def source(data,name):return {'name':name,'base64':base64.b64encode(data).decode()}
def sample():
    from datetime import datetime,timezone
    now=datetime.now(timezone.utc).isoformat();s=ingest({'source':source(b'id,latitude,longitude\n001,53.54123,-113.4978\n','obs.csv')});r=s['resource'];r['id']='r1';t=s['tables'][0];t.update({'id':'t1','resourceId':'r1','columns':[{'workingName':h,'description':'','dataType':'string','status':'Unknown','unit':'','term':'','allowedValues':[],'constraints':{},'evidence':[]} for h in t['headers']],'primaryKey':['id'],'originalTable':{'headers':t['headers'].copy(),'rows':[row.copy() for row in t['rows']]}})
    for c,term in zip(t['columns'][1:],['decimalLatitude','decimalLongitude']):c['term']=term;c['status']='Confirmed'
    return {'version':2,'id':'p1','revision':0,'createdAt':now,'updatedAt':now,'metadata':{k:{'value':v,'status':'Confirmed','evidence':[],'rationale':'Test'} for k,v in {'title':'Test','description':'Test dataset','creator':'Test organization','organizations':'Test organization','contact':'Test organization','license':'CC0-1.0','publicationDate':'2026-09-30'}.items()},'resources':[r],'tables':[t],'relationships':[],'audit':[],'undoStack':[],'redoStack':[],'profiles':{'frictionless':'1','eml':'2.2.0','roCrate':'1.2'}}

class ImportTests(unittest.TestCase):
    def test_empty_supporting_file_is_still_preserved(self):
        r=ingest({'source':source(b'','lost_notes.txt'),'options':{'preserveOnly':True}})
        self.assertEqual(r['resource']['bytes'],0);self.assertEqual(r['resource']['sha256'],sha(b''));self.assertEqual(r['tables'],[])
    def test_unsupported_and_malformed_still_preserved(self):
        for data,name in [(b'legacy binary','old.xls'),(b'%PDF context','protocol.pdf'),(b'a,b\n"broken','bad.csv')]:
            result=ingest({'source':source(data,name)})
            self.assertEqual(result['resource']['sha256'],sha(data));self.assertTrue(result['resource']['conversionIssue']);self.assertEqual(result['tables'],[])

    def test_semicolon_legacy_encoding_and_supporting_text(self):
        result=ingest({'source':source('site;count\nforêt;0'.encode('cp1252'),'old.csv'),'options':{'delimiter':';','encoding':'cp1252'}})
        self.assertEqual(result['tables'][0]['rows'],[['forêt','0']]);self.assertTrue(result['tables'][0]['parsing']['strict'])
        self.assertEqual(ingest({'source':source(b'field protocol','notes.txt'),'options':{'preserveOnly':True}})['tables'],[])

    def test_json_multiple_record_arrays_and_nested_context(self):
        result=ingest({'source':source(json.dumps({'events':[{'id':'E1'}],'obs':[{'event':'E1','context':{'age':'adult'}}],'note':'unknown'}).encode(),'data.json')})
        self.assertEqual(len(result['tables']),2);self.assertIn('adult',result['tables'][1]['rows'][0][1]);self.assertIn('retained',result['resource']['archaeology']['notes'][0])

    def test_sqlite_multitable_readonly_blob_preservation(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'a.db';conn=sqlite3.connect(path);conn.execute('CREATE TABLE events (id TEXT PRIMARY KEY)');conn.execute("INSERT INTO events VALUES ('E1')");conn.execute('CREATE TABLE obs (event TEXT, geometry BLOB)');conn.execute('INSERT INTO obs VALUES (?,?)',('E1',b'\x00\x01'));conn.commit();conn.close();data=path.read_bytes()
        r=ingest({'source':source(data,'survey.gpkg')});self.assertEqual(len(r['tables']),2);self.assertTrue(r['tables'][1]['rows'][0][1].startswith('base64:'));self.assertEqual(r['resource']['sha256'],sha(data))

    def test_excel_hidden_sheets_formula_comments_merges(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:
            z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><workbookPr date1904="1"/><sheets><sheet name="Data" r:id="r1"/><sheet name="Clues" state="hidden" r:id="r2"/></sheets></workbook>')
            z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/><Relationship Id="r2" Target="worksheets/sheet2.xml"/></Relationships>')
            z.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>id</t></is></c></row><row r="2"><c r="A2"><f>1+1</f><v>2</v></c></row></sheetData><mergeCells><mergeCell ref="B1:C1"/></mergeCells></worksheet>')
            z.writestr('xl/worksheets/sheet2.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c t="inlineStr"><is><t>notes</t></is></c></row><row r="2"><c t="inlineStr"><is><t>Context</t></is></c></row></sheetData></worksheet>')
            z.writestr('xl/worksheets/_rels/sheet1.xml.rels','<Relationships><Relationship Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" Target="../comments1.xml"/></Relationships>')
            z.writestr('xl/comments1.xml','<comments xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><authors><author>Recorder</author></authors><commentList><comment ref="A2" authorId="0"><text><t>Count confirmed</t></text></comment></commentList></comments>')
        r=ingest({'source':source(b.getvalue(),'old.xlsx')});self.assertEqual(len(r['tables']),2);a=r['resource']['archaeology'];self.assertEqual(a['dateSystem'],'1904');self.assertEqual(a['sheets'][1]['state'],'hidden');self.assertEqual(a['sheets'][0]['formulas'][0]['formula'],'1+1');self.assertEqual(a['sheets'][0]['comments'][0]['text'],'Count confirmed');self.assertEqual(a['sheets'][0]['mergedCells'],['B1:C1'])

    def test_ods_multi_sheet_import(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:z.writestr('content.xml','<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><office:body><office:spreadsheet><table:table table:name="Data"><table:table-row><table:table-cell><text:p>id</text:p></table:table-cell></table:table-row><table:table-row><table:table-cell><text:p>001</text:p></table:table-cell></table:table-row></table:table></office:spreadsheet></office:body></office:document-content>')
        result=ingest({'source':source(b.getvalue(),'survey.ods')});self.assertEqual(result['tables'][0]['rows'],[['001']]);self.assertEqual(result['tables'][0]['sheet'],'Data')

class StorageExportTests(unittest.TestCase):
    def test_atomic_saves_previous_recovery_and_original_integrity(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(d);p=store.save(sample());self.assertEqual(p['revision'],1);self.assertTrue(store.verify(p)[0]['diskMatches']);p['metadata']['title']['value']='New';next=store.save(p);self.assertEqual(next['revision'],2);self.assertEqual(store.get('p1',True)['metadata']['title']['value'],'Test');self.assertEqual(store.list()[0]['title'],'New')
            with self.assertRaisesRegex(ValueError,'conflict'):store.save(p)
            next['resources'][0]['base64']=base64.b64encode(b'changed').decode();next['resources'][0]['sha256']=sha(b'changed');next['resources'][0]['bytes']=len(b'changed')
            with self.assertRaisesRegex(ValueError,'overwritten'):store.save(next)

    def test_import_baseline_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(d);p=store.save(sample());p['tables'][0]['originalTable']['rows'][0][0]='fake'
            with self.assertRaisesRegex(ValueError,'baselines'):store.save(p)

    def test_archive_tampering_is_detected_not_silently_repaired(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(d);p=store.save(sample());r=p['resources'][0];(Path(d)/'originals'/r['sha256']).write_bytes(b'bad');self.assertFalse(store.verify(p)[0]['diskMatches'])
            with self.assertRaisesRegex(ValueError,'Archived original'):store.save(p)

    def test_private_export_backup_report_schemas_eml_and_rocrate(self):
        p=sample();blob=export_v2({'project':p})
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            self.assertIn('rescue-report.md',z.namelist());self.assertIn('eml-draft.xml',z.namelist());self.assertIn('ro-crate-metadata.json',z.namelist());self.assertEqual(json.loads(z.read('project.biorescue.json')),p)
            descriptor=json.loads(z.read('datapackage.json'));self.assertEqual(descriptor['resources'][0]['schema']['primaryKey'],['id']);self.assertEqual(z.read('working/t1-obs.csv').decode().splitlines()[1],'001,53.54123,-113.4978')
            for line in z.read('checksums.sha256').decode().splitlines():digest,name=line.split('  ',1);self.assertEqual(sha(z.read(name)),digest)
            self.assertEqual(json.loads(z.read('eml-status.json'))['xsdValidated'],json.loads(z.read('eml-xsd-validation.json')).get('xsdValidated',False))

    def test_public_export_never_contains_originals_or_private_snapshots(self):
        p=sample();before=json.dumps(p)
        for mode in ('redact','generalize'):
            with zipfile.ZipFile(io.BytesIO(export_v2({'project':p,'policy':{'mode':mode,'precision':1}}))) as z:
                for forbidden in ['project.biorescue.json','audit.json','metadata.json','fields.json','source-manifest.json','rescue-report.md']:self.assertNotIn(forbidden,z.namelist())
                self.assertFalse(any(name.startswith('original/') for name in z.namelist()))
                row=z.read('working/t1-obs.csv').decode().splitlines()[1]
                self.assertEqual(row,'001,,' if mode=='redact' else '001,53.5,-113.5')
                self.assertNotIn('primaryKey',json.loads(z.read('datapackage.json'))['resources'][0]['schema'])
        self.assertEqual(json.dumps(p),before)

    def test_strict_exports_block_broken_declared_keys(self):
        p=sample();p['tables'][0]['rows'].append(p['tables'][0]['rows'][0].copy());self.assertTrue(any(c['severity']=='Error' for c in structure_checks(p)))
        with self.assertRaisesRegex(ValueError,'block strict'):export_v2({'project':p,'strict':True})
        self.assertTrue(export_v2({'project':p,'strict':False}))

    def test_public_redaction_covers_unmapped_and_renamed_short_coordinates(self):
        p=sample();t=p['tables'][0];t['headers'][1]='mystery';t['headers'][2]='site_lon';t['columns'][1]['originalName']='lat';t['columns'][1]['term']='';t['columns'][1]['status']='Unknown';t['columns'][2]['term']='';t['columns'][2]['status']='Unknown'
        with zipfile.ZipFile(io.BytesIO(export_v2({'project':p,'policy':{'mode':'redact'}}))) as z:self.assertEqual(z.read('working/t1-obs.csv').decode().splitlines()[1],'001,,')

    def test_unconfirmed_metadata_never_becomes_standard_assertions(self):
        p=sample();p['metadata']['creator']['status']='Inferred';p['tables'][0]['columns'][1]['status']='Inferred'
        with zipfile.ZipFile(io.BytesIO(export_v2(p))) as z:
            self.assertNotIn('eml-draft.xml',z.namelist());self.assertNotIn('ro-crate-metadata.json',z.namelist());self.assertNotIn('dcterms:isVersionOf',json.loads(z.read('datapackage.json'))['resources'][0]['schema']['fields'][1])

    def test_no_runtime_remote_assets_or_connections(self):
        root=Path(__file__).resolve().parents[1]
        for file in ['web/index.html','web/app2.mjs','web/project.mjs','web/styles.css','web/upgrade.css']:
            data=(root/file).read_text(encoding='utf-8');self.assertNotIn('fetch("http',data);self.assertNotIn("fetch('http",data);self.assertNotIn('src="https:',data);self.assertNotIn('@import',data)
        self.assertIn("connect-src 'self'",(root/'server.py').read_text())
