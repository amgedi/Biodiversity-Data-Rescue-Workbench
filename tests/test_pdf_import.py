import base64,io,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'vendor'))
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject,ArrayObject,TextStringObject
from importers import ingest
from pdf_import import recovered,verify_vendor,_slots
from pdf_limits import WindowsJob
from worker_runtime import worker_interpreter
def fictional_pdf(text='Fictional protocol: 001, NA and 0 are literal.',encrypted=False):
 writer=PdfWriter();page=writer.add_blank_page(width=600,height=800);font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')});page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})});stream=DecodedStreamObject();stream.set_data(('BT /F1 12 Tf 50 750 Td ('+text.replace('\\','\\\\').replace('(','\\(').replace(')','\\)')+') Tj ET').encode());page[NameObject('/Contents')]=writer._add_object(stream);writer.add_metadata({'/Title':'Fictional protocol with uncertain sampling'});writer._root_object[NameObject('/OpenAction')]=DictionaryObject({NameObject('/S'):NameObject('/JavaScript'),NameObject('/JS'):TextStringObject('Fictional passive action; never execute.')})
 if encrypted:writer.encrypt('fictional-password')
 output=io.BytesIO();writer.write(output);return output.getvalue()
class PdfImportTests(unittest.TestCase):
 def source(self,raw):return {'name':'fictional.pdf','base64':base64.b64encode(raw).decode()}
 def test_actual_bounded_worker_recovers_page_cited_literal_text_without_a_scientific_table(self):
  raw=fictional_pdf();result=ingest({'source':self.source(raw)});preview=result['resource']['archaeology']['documentPreview'];self.assertNotIn('reasonCode',preview);self.assertEqual(preview['reader']['version'],'6.19.0');self.assertEqual(preview['blocks'][0]['page'],1);self.assertIn('001, NA and 0',preview['blocks'][0]['text']);self.assertEqual(preview['limits']['memoryBytes'],256*1024*1024);self.assertEqual(base64.b64decode(result['resource']['base64']),raw);self.assertEqual(result['tables'],[]);self.assertEqual(preview['documentProperties']['/Title'],'Fictional protocol with uncertain sampling')
 def test_protected_invalid_and_textless_documents_preserve_original_without_ocr_or_passwords(self):
  for raw,code in [(fictional_pdf(encrypted=True),'PDF_ENCRYPTED'),(b'%PDF-invalid fictional original','PDF_INVALID')]:
   result=ingest({'source':self.source(raw)});self.assertEqual(result['resource']['archaeology']['documentPreview']['reasonCode'],code);self.assertEqual(base64.b64decode(result['resource']['base64']),raw)
  writer=PdfWriter();writer.add_blank_page(width=200,height=200);output=io.BytesIO();writer.write(output);preview=ingest({'source':self.source(output.getvalue())})['resource']['archaeology']['documentPreview'];self.assertTrue(preview['blocks'][0]['noRecoveredText']);self.assertEqual(preview['previewPagesWithoutRecoveredText'],1)
 def test_excerpt_limits_and_preserve_only_keep_full_original(self):
  raw=fictional_pdf('x'*4500);preview=ingest({'source':self.source(raw)})['resource']['archaeology']['documentPreview'];self.assertEqual(len(preview['blocks'][0]['text']),4000);self.assertTrue(preview['blocks'][0]['truncated'])
  with patch('pdf_import.recovered',side_effect=AssertionError('Reader must not run')):result=ingest({'source':self.source(raw),'options':{'preserveOnly':True}})
  self.assertNotIn('documentPreview',result['resource']['archaeology'])
 def test_busy_integrity_failure_and_timeout_keep_source(self):
  _slots.acquire();_slots.acquire()
  try:self.assertEqual(recovered(fictional_pdf())['error'],'PDF_BUSY')
  finally:_slots.release();_slots.release()
  with patch('pdf_import.verify_vendor',side_effect=ValueError('Corrupt pinned reader')):self.assertEqual(recovered(fictional_pdf())['error'],'PDF_READER_INTEGRITY')
  with patch('pdf_import.subprocess.Popen') as factory:
   process=factory.return_value;process.communicate.side_effect=[subprocess.TimeoutExpired('fictional worker',20),(b'',None)];process.poll.return_value=0
   with patch('pdf_import.WindowsJob'):self.assertEqual(recovered(fictional_pdf())['error'],'PDF_TIMEOUT')
   process.kill.assert_called_once()
  if os.name=='nt':
   with patch('pdf_import.subprocess.Popen') as factory:
    process=factory.return_value;process.poll.return_value=0;process.communicate.return_value=(b'',None)
    with patch('pdf_import.WindowsJob',side_effect=OSError('Fictional containment failure')):self.assertEqual(recovered(fictional_pdf())['error'],'PDF_LIMIT_UNAVAILABLE')
    process.kill.assert_called_once();process.communicate.assert_called_once()
 @unittest.skipUnless(os.name=='nt','Windows committed-memory job acceptance')
 def test_windows_memory_limit_precedes_processing_and_blocks_large_allocation(self):
  process=subprocess.Popen([worker_interpreter(),'-X','utf8','-c','import sys; sys.stdin.readline();\ntry: value=bytearray(256*1024*1024); print("UNBOUNDED")\nexcept MemoryError: print("BOUNDED")'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW);job=None
  try:job=WindowsJob(process,memory=96*1024*1024);output,_=process.communicate(b'go\n',timeout=5);self.assertEqual(output.strip(),b'BOUNDED')
  finally:
   if process.poll() is None:process.kill();process.communicate()
   if job:job.close()
 def test_pinned_reader_inventory_and_license_are_verified(self):verify_vendor()
 def test_page_preview_and_logical_page_limits_are_explicit(self):
  for count in [51,2001]:
   writer=PdfWriter()
   for _ in range(count):writer.add_blank_page(width=200,height=200)
   output=io.BytesIO();writer.write(output);result=ingest({'source':self.source(output.getvalue())});preview=result['resource']['archaeology']['documentPreview']
   if count==51:self.assertEqual(preview['previewPages'],50);self.assertEqual(preview['omittedPages'],1);self.assertEqual(preview['blocks'][-1]['page'],50)
   else:self.assertEqual(preview['reasonCode'],'PDF_PAGE_LIMIT')
   self.assertEqual(base64.b64decode(result['resource']['base64']),output.getvalue())
