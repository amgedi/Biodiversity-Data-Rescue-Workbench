import base64,gzip,hashlib,io,json,tarfile,unittest,zipfile
from importers import ingest
from document_imports import xml_tree
def source(name,raw):return {'name':name,'base64':base64.b64encode(raw).decode()}
class DocumentImportTests(unittest.TestCase):
 def test_xml_inventory_never_selects_a_record_path_or_scientific_meaning(self):
  raw=b'<dataset><record><site>001</site><count>0</count></record><record><site>NA</site><count> 0 </count></record></dataset>';result=ingest({'source':source('fictional.xml',raw)})
  self.assertEqual(result['tables'],[]);self.assertEqual(result['resource']['role'],'supporting');self.assertIsNone(result['resource']['conversionIssue']);self.assertEqual(result['resource']['sha256'],hashlib.sha256(raw).hexdigest());paths=result['resource']['archaeology']['xml']['recordPaths'];self.assertIn({'path':['dataset','record'],'records':2,'attributes':[]},paths)
 def test_explicit_namespace_path_retains_literal_attributes_whitespace_and_empty_distinctions(self):
  raw=b'<d:dataset xmlns:d="urn:fictional"><d:record id="001"><d:count>0</d:count><d:note> NA </d:note></d:record><d:record id="0"><d:count/></d:record></d:dataset>';result=ingest({'source':source('fictional.xml',raw),'options':{'xmlRecordPath':['{urn:fictional}dataset','{urn:fictional}record']}});table=result['tables'][0]
  self.assertEqual(table['headers'],['@id','{urn:fictional}count','{urn:fictional}note']);self.assertEqual(table['rows'],[['001','0',' NA '],['0','','']]);self.assertIn('Absent and empty',table['parsing']['emptyPolicy']);self.assertEqual(result['resource']['base64'],base64.b64encode(raw).decode())
 def test_repeated_mixed_nested_fields_and_unknown_path_preserve_original_without_a_table(self):
  for raw,path in [(b'<d><r><v>0</v><v>1</v></r></d>',['d','r']),(b'<d><r>meaning<v>0</v></r></d>',['d','r']),(b'<d><r><v unit="m">0</v></r></d>',['d','r']),(b'<d><r><v><x>0</x></v></r></d>',['d','r']),(b'<d><r>0</r></d>',['absent'])]:
   with self.subTest(raw=raw):
    result=ingest({'source':source('fictional.xml',raw),'options':{'xmlRecordPath':path}});self.assertEqual(result['tables'],[]);self.assertTrue(result['resource']['conversionIssue']);self.assertEqual(base64.b64decode(result['resource']['base64']),raw)
 def test_declarations_rejected_in_utf8_and_utf16_without_entity_expansion(self):
  text='<!DOCTYPE d [<!ENTITY secret SYSTEM "file:///C:/fictional-secret">]><d>&secret;</d>'
  for encoding in ['utf-8','utf-16','utf-32','utf-16-le','utf-16-be']:
   result=ingest({'source':source('fictional.xml',text.encode(encoding))});self.assertEqual(result['tables'],[]);self.assertTrue(result['resource']['conversionIssue']);self.assertNotIn('fictional-secret',str(result['resource']['archaeology']))
 def test_xml_depth_and_path_inventory_are_bounded(self):
  for raw in [b'<d>'*65+b'0'+b'</d>'*65,b'<d>'+b''.join(f'<v{i}>0</v{i}>'.encode() for i in range(201))+b'</d>']:
   result=ingest({'source':source('fictional.xml',raw)});self.assertEqual(result['tables'],[]);self.assertTrue(result['resource']['conversionIssue'])
 def word(self):
  buffer=io.BytesIO()
  with zipfile.ZipFile(buffer,'w') as archive:
   archive.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Fictional protocol: </w:t><w:tab/><w:t>001 is literal.</w:t></w:r><w:del w:author="A"><w:r><w:delText>old meaning</w:delText></w:r></w:del><w:ins w:author="B"><w:r><w:t>new proposal</w:t></w:r></w:ins></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>NA</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>0</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>');archive.writestr('word/comments.xml','<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:comment w:id="0" w:author="Curator"><w:p><w:r><w:t>Uncertain sampling method</w:t></w:r></w:p></w:comment></w:comments>');archive.writestr('word/vbaProject.bin',b'Fictional passive macro bytes')
  return buffer.getvalue()
 def test_word_preview_retains_changes_comments_literal_tables_and_exact_original(self):
  raw=self.word();result=ingest({'source':source('fictional.docm',raw)});preview=result['resource']['archaeology']['documentPreview'];self.assertEqual(result['tables'],[]);self.assertEqual(preview['blocks'][1]['rows'],[['NA','0']]);self.assertIn('\t001',preview['blocks'][0]['text']);self.assertEqual([c['kind'] for c in preview['trackedChanges']],['deleted','inserted']);self.assertEqual(preview['comments'][0]['text'],'Uncertain sampling method');self.assertTrue(result['resource']['archaeology']['container']['macroPartsPresent']);self.assertEqual(base64.b64decode(result['resource']['base64']),raw)
 def test_word_preview_caps_large_paragraphs_and_preserve_only_skips_extraction(self):
  buffer=io.BytesIO()
  with zipfile.ZipFile(buffer,'w') as archive:archive.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'+('x'*4500)+'</w:t></w:r></w:p></w:body></w:document>')
  raw=buffer.getvalue();result=ingest({'source':source('fictional.docx',raw)});block=result['resource']['archaeology']['documentPreview']['blocks'][0];self.assertTrue(block['truncated']);self.assertEqual(len(block['text']),4000);preserved=ingest({'source':source('fictional.docx',raw),'options':{'preserveOnly':True}});self.assertNotIn('documentPreview',preserved['resource']['archaeology'])
 def test_tar_and_gzip_inventory_retain_duplicates_links_and_unsafe_names_without_extraction(self):
  buffer=io.BytesIO()
  with tarfile.open(fileobj=buffer,mode='w') as archive:
   for name in ['observations.csv','observations.csv','../retained-unsafe.txt']:
    info=tarfile.TarInfo(name);info.size=3;archive.addfile(info,io.BytesIO(b'001'))
   link=tarfile.TarInfo('link');link.type=tarfile.SYMTYPE;link.linkname='/fictional/external';archive.addfile(link)
  for name,raw in [('fictional.tar',buffer.getvalue()),('fictional.tar.gz',gzip.compress(buffer.getvalue()))]:
   result=ingest({'source':source(name,raw)});members=result['resource']['archaeology']['members'];self.assertEqual(len(members),4);self.assertTrue(members[1]['duplicateName']);self.assertTrue(members[2]['unsafePath']);self.assertEqual(members[3]['kind'],'symbolic link');self.assertEqual(result['tables'],[]);self.assertEqual(base64.b64decode(result['resource']['base64']),raw)
 def test_tar_declared_oversize_is_blocked_before_reading_member_payload(self):
  member=tarfile.TarInfo('fictional-too-large.bin');member.size=20*1024*1024+1;raw=member.tobuf()+b'\x00'*1024;result=ingest({'source':source('fictional.tar',raw)});self.assertEqual(result['tables'],[]);self.assertIn('DOCUMENT_TAR_LIMIT',result['resource']['conversionIssue']);self.assertEqual(base64.b64decode(result['resource']['base64']),raw)
 def test_word_comments_changes_and_unsupported_blocks_expose_preview_boundaries(self):
  buffer=io.BytesIO();namespace='xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
  with zipfile.ZipFile(buffer,'w') as archive:
   archive.writestr('word/document.xml','<w:document '+namespace+'><w:body><w:p>'+''.join('<w:ins><w:r><w:t>'+('x'*2001)+'</w:t></w:r></w:ins>' for _ in range(201))+'</w:p><w:sdt><w:p><w:r><w:t>Not reconstructed</w:t></w:r></w:p></w:sdt></w:body></w:document>');archive.writestr('word/comments.xml','<w:comments '+namespace+'>'+''.join('<w:comment><w:p><w:r><w:t>'+('c'*4001)+'</w:t></w:r></w:p></w:comment>' for _ in range(201))+'</w:comments>')
  result=ingest({'source':source('fictional.docx',buffer.getvalue())});preview=result['resource']['archaeology']['documentPreview'];self.assertEqual(preview['totalComments'],201);self.assertEqual(preview['omittedComments'],1);self.assertEqual(len(preview['comments']),200);self.assertTrue(preview['comments'][0]['truncated']);self.assertEqual(preview['totalTrackedChanges'],201);self.assertEqual(preview['omittedTrackedChanges'],1);self.assertTrue(preview['trackedChanges'][0]['truncated']);self.assertEqual(sum(preview['unsupportedBodyNodes'].values()),1)
