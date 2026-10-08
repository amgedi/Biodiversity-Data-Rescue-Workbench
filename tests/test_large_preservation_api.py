import base64,http.client,io,json,zipfile,unittest
import test_editing_api
from large_preservation import metadata

class LargePreservationApiTests(unittest.TestCase):
 call=test_editing_api.EditingApiTests.call
 tearDown=test_editing_api.EditingApiTests.tearDown
 def setUp(self):
  test_editing_api.EditingApiTests.setUp(self);self.raw=b'id,count\n001,0\n002,NA\n';job=self.server.large.create('fictional.csv',len(self.raw));self.id=job['id'];self.server.large.chunk(self.id,0,base64.b64encode(self.raw).decode());self.server.large.start(self.id,False)
 def large_claim(self,session,**extra):return self.call('/api/edit-session',{'projectId':'large:'+self.id,'session':session,'action':'claim',**extra})[1]
 def change(self,proof=None,**extra):return self.call('/api/large-metadata',dict(id=self.id,workingRevision=0,metadataRevision=0,reviewer='Fictional curator',reason='Fictional reviewed definition',changes=[dict(kind='field',column=1,description='Literal recorded count',unit='',dataType='integer',status='Confirmed')],**extra),proof)
 def get(self,path):
  c=http.client.HTTPConnection('127.0.0.1',self.server.server_port);c.request('GET',path);r=c.getresponse();result=r.status,dict(r.headers),r.read();c.close();return result
 def test_large_metadata_requires_current_window_authority(self):
  one=self.large_claim('window-one');self.assertEqual(self.change()[0],400);two=self.large_claim('window-two',action='takeover',generation=one['generation']);self.assertTrue(two['editing']);self.assertEqual(self.change(one)[0],400);self.assertEqual(self.change(two)[0],200);self.assertEqual(metadata(self.server.large,self.id)['metadataRevision'],1)
 def test_revision_conflict_rejects_write_without_history_change(self):
  one=self.large_claim('window-one');self.assertEqual(self.change(one)[0],200);status,result=self.change(one);self.assertEqual(status,400);self.assertIn('LARGE_METADATA_STALE',result['error']);self.assertEqual(metadata(self.server.large,self.id)['metadataRevision'],1)
 def test_download_is_verified_before_zip_headers_and_rejects_corrupt_original(self):
  status,headers,body=self.get('/api/large-package?id='+self.id);self.assertEqual(status,200);self.assertEqual(headers['Content-Type'],'application/zip');self.assertEqual(int(headers['Content-Length']),len(body));self.assertEqual(headers['Cache-Control'],'no-store')
  with zipfile.ZipFile(io.BytesIO(body)) as archive:self.assertEqual(archive.read('sources/original.bin'),self.raw)
  (self.server.large.folder(self.id)/'original.bin').write_bytes(b'fictional corruption');status,headers,body=self.get('/api/large-package?id='+self.id);self.assertEqual(status,400);self.assertIn('LARGE_SOURCE_INTEGRITY',json.loads(body)['error']);self.assertIn('application/json',headers['Content-Type'])
 def test_batch_preview_and_commit_respect_authority_and_exact_revision(self):
  one=self.large_claim('window-one');self.server.large.edit(self.id,0,row=1,column=0,value=' 001 ',expected='001',reason='Fictional edge whitespace');payload={'id':self.id,'operation':'trim-whitespace','columns':[0]};status,proposal=self.call('/api/large-batch-preview',payload);self.assertEqual(status,200);self.assertEqual(proposal['changedCells'],1);reviewed={**payload,**proposal,'reason':'Reviewed fictional whitespace','reviewer':'Fictional curator'};self.assertEqual(self.call('/api/large-batch-trim',reviewed)[0],400);self.assertEqual(self.call('/api/large-batch-trim',reviewed,one)[0],200);self.assertEqual(self.call('/api/large-batch-trim',reviewed,one)[0],400);self.assertEqual(self.server.large.page(self.id)['rows'][0]['values'],['001','0'])
