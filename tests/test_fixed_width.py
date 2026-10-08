import base64,unittest
from unittest.mock import patch
from importers import ingest

class FixedWidthTests(unittest.TestCase):
 def run_import(self,text,widths,header=0,encoding='utf-8',name='fictional.fwf'):
  raw=text.encode(encoding);return raw,ingest({'source':{'name':name,'base64':base64.b64encode(raw).decode()},'options':{'textFormat':'fixed-width','fixedWidths':widths,'encoding':encoding,'headerRow':header}})
 def test_literal_headerless_first_record_spaces_and_zero_are_retained(self):
  raw,result=self.run_import('001NA 0\r\n002   1\r\n',[3,3,1]);table=result['tables'][0];self.assertEqual(table['rows'],[['001','NA ','0'],['002','   ','1']]);self.assertEqual(table['headers'],['column_1','column_2','column_3']);self.assertEqual(base64.b64decode(result['resource']['base64']),raw);self.assertFalse(table['parsing']['stripValues'])
 def test_header_preamble_duplicate_and_blank_headers_are_reproducible(self):
  _,result=self.run_import('Fictional preamble\nIDID  \n01NA  \n',[2,2,2],header=2);t=result['tables'][0];self.assertEqual(t['headers'],['ID','ID_2','  ']);self.assertEqual(t['rows'],[['01','NA','  ']]);self.assertEqual(t['parsing']['preambleLines'],1)
 def test_unicode_is_character_positions_not_encoded_bytes_or_visual_columns(self):
  for encoding in ['utf-8','utf-16','cp1252','latin-1']:
   _,r=self.run_import('é01\rü00',[1,2],encoding=encoding);self.assertEqual(r['tables'][0]['rows'],[['é','01'],['ü','00']])
  _,r=self.run_import('e\u030101\n\t 00',[2,2]);self.assertEqual(r['tables'][0]['rows'],[['e\u0301','01'],['\t ','00']])
 def test_short_long_blank_or_extra_fields_block_whole_conversion(self):
  for text in ['0010\n002','0010\n00200','0010\n\n0020']:
   raw,r=self.run_import(text,[3,1]);self.assertEqual(r['tables'],[]);self.assertEqual(r['resource']['archaeology']['fixedWidthReview']['reasonCode'],'FW_LENGTH');self.assertEqual(base64.b64decode(r['resource']['base64']),raw)
 def test_explicit_width_encoding_header_and_resource_bounds(self):
  for widths in [None,[],[0],[True],[1.0],['3'],[65537],[1]*251,[40000,40000]]:
   _,r=self.run_import('0010',widths);self.assertEqual(r['tables'],[]);self.assertEqual(r['resource']['archaeology']['fixedWidthReview']['reasonCode'],'FW_WIDTHS')
  _,r=self.run_import('0010',[3,1],encoding='utf-8');self.assertEqual(r['tables'][0]['parsing']['offsetUnit'],'decoded Unicode code points')
  source={'name':'fictional.fwf','base64':base64.b64encode(b'0010').decode()}
  for option,code in [({'encoding':'auto'},'FW_ENCODING'),({'headerRow':True},'FW_HEADER'),({'headerRow':1001},'FW_HEADER')]:
   r=ingest({'source':source,'options':{'fixedWidths':[3,1],'encoding':'utf-8','headerRow':0,**option}});self.assertEqual(r['resource']['archaeology']['fixedWidthReview']['reasonCode'],code)
  with patch('fixed_width.MAX_ROWS',2):
   _,r=self.run_import('0010\n0020\n0030',[3,1]);self.assertEqual(r['tables'],[]);self.assertEqual(r['resource']['archaeology']['fixedWidthReview']['reasonCode'],'FW_ROWS')
  _,r=self.run_import('0\x0001',[3,1]);self.assertEqual(r['resource']['archaeology']['fixedWidthReview']['reasonCode'],'FW_NUL')
 def test_preserve_only_and_default_delimited_input_remain_separate(self):
  s={'name':'fictional.txt','base64':base64.b64encode(b'id,value\n001,NA').decode()};r=ingest({'source':s});self.assertEqual(r['tables'][0]['rows'],[['001','NA']]);r=ingest({'source':s,'options':{'preserveOnly':True,'textFormat':'fixed-width'}});self.assertEqual(r['tables'],[]);self.assertEqual(r['resource']['base64'],s['base64'])
