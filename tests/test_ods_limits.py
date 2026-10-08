import unittest,io,zipfile,base64
from importers import import_ods
def source(cells,repeat=1):
 xml=f'<o:document-content xmlns:o="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:t="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:x="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><o:body><o:spreadsheet><t:table t:name="Synthetic"><t:table-row t:number-rows-repeated="{repeat}">{cells}</t:table-row></t:table></o:spreadsheet></o:body></o:document-content>'
 data=io.BytesIO()
 with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('content.xml',xml)
 return {'name':'synthetic.ods','base64':base64.b64encode(data.getvalue()).decode()}
def cell(repeat):return f'<t:table-cell t:number-columns-repeated="{repeat}"><x:p>literal</x:p></t:table-cell>'
class OdsBounds(unittest.TestCase):
 def test_aggregate_width_rejected_before_row_repetition(self):
  with self.assertRaisesRegex(ValueError,'column limit'):import_ods(source(cell(250)+cell(1),100000),{})
 def test_nonpositive_repetitions_rejected(self):
  for count in (0,-1):
   with self.assertRaises(ValueError):import_ods(source(cell(count)),{})
   with self.assertRaises(ValueError):import_ods(source(cell(1),count),{})
 def test_cell_budget_rejected_before_allocating_rows(self):
  with self.assertRaisesRegex(ValueError,'cell limit'):import_ods(source(cell(250),100000),{})
 def test_small_repeated_rows_preserve_literal_values(self):
  tables,details=import_ods(source(cell(2),3),{})
  self.assertEqual(details['sheets'][0]['firstRows'],[['literal','literal']]*3)
  self.assertEqual(len(tables),1)
