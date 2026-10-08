import copy,io,json,unittest,zipfile
from test_upgrade import sample
from report_v3 import report_data,report_html,report_markdown
from localization import message,catalog,LANGUAGES
from exporters import export_v2
class LocalizedReportTests(unittest.TestCase):
 def test_all_offline_report_catalogs_have_exact_keys_and_placeholders(self):
  import re
  english=catalog()
  for locale in LANGUAGES:
   target=catalog(locale);self.assertEqual(set(target),set(english),locale)
   for key,text in english.items():self.assertEqual(sorted(re.findall(r'\{[^}]+\}',text)),sorted(re.findall(r'\{[^}]+\}',target[key])),(locale,key))
 def test_report_labels_translate_and_evidence_and_scientific_values_stay_literal(self):
  p=sample();p['metadata']['description']['value']='001 Rana temporaria NA zéro حدث';before=copy.deepcopy(p)
  report=report_data(p,[{'code':'RO-GRAPH','severity':'Error','description':'@graph must be an array.'}],'fr')
  self.assertEqual(report['metadata'],p['metadata']);self.assertEqual(report['validation'][0]['description'],'@graph must be an array.')
  self.assertNotEqual(report['displayValidation'][0]['description'],report['validation'][0]['description'])
  html=report_html(report).decode();self.assertIn('lang="fr"',html);self.assertIn('001 Rana temporaria NA zéro حدث',html);self.assertNotIn('Technical validity is not scientific correctness.',html);self.assertEqual(p,before)
 def test_arabic_exports_are_rtl_without_translating_original_bytes_or_internal_state(self):
  p=sample();before=copy.deepcopy(p)
  with zipfile.ZipFile(io.BytesIO(export_v2({'project':p,'reportLanguage':'ar'}))) as archive:
   self.assertIn('dir="rtl"',archive.read('rescue-report.html').decode());self.assertEqual(json.loads(archive.read('project.biorescue.json')),p);self.assertEqual(json.loads(archive.read('rescue-report.json'))['reportLanguage'],'ar')
  self.assertEqual(p,before)
 def test_unknown_report_language_rejects_instead_of_claiming_localized_output(self):
  with self.assertRaisesRegex(ValueError,'Unsupported report language'):report_data(sample(),[],'xx')
