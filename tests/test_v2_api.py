import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from server import Handler
from storage import Store
from test_upgrade import sample

class V2ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.store=Store(self.temp.name);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
    def call(self,path,p=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port);conn.request('GET' if p is None else 'POST',path,None if p is None else json.dumps(p),{} if p is None else {'Content-Type':'application/json'});r=conn.getresponse();status,data=r.status,r.read();conn.close();return status,data
    def test_save_reopen_verify_and_previous_revision(self):
        status,data=self.call('/api/save',sample());self.assertEqual(status,200);p=json.loads(data);self.assertEqual(p['revision'],1)
        self.assertEqual(json.loads(self.call('/api/projects')[1])[0]['id'],'p1');self.assertEqual(json.loads(self.call('/api/project?id=p1')[1]),p)
        self.assertTrue(json.loads(self.call('/api/verify',p)[1])[0]['diskMatches']);p['metadata']['title']['value']='Revision two';self.assertEqual(self.call('/api/save',p)[0],200)
        self.assertEqual(json.loads(self.call('/api/project?id=p1&previous=1')[1])['metadata']['title']['value'],'Test')
    def test_backup_can_open_in_independent_installation(self):
        p=json.loads(self.call('/api/save',sample())[1])
        with tempfile.TemporaryDirectory() as second:
            other=Store(second);opened=other.save(json.loads(json.dumps(p)));self.assertTrue(other.verify(opened)[0]['diskMatches']);self.assertEqual(opened['resources'],p['resources'])
    def test_original_overwrite_is_rejected_through_api(self):
        p=json.loads(self.call('/api/save',sample())[1]);p['resources'][0]['name']='different.csv';status,data=self.call('/api/save',p);self.assertEqual(status,400);self.assertIn(b'cannot be overwritten',data)
    def test_export_api_returns_binary_zip_for_public_and_private(self):
        for mode in ('private','redact'):
            status,data=self.call('/api/export',{'project':sample(),'policy':{'mode':mode}});self.assertEqual(status,200);self.assertTrue(data.startswith(b'PK'))
    def test_sources_never_exposed_as_static_files(self):
        self.call('/api/save',sample());self.assertEqual(self.call('/local-data/projects/p1.json')[0],404)
        self.assertEqual(self.call('/api/project?id=../../server.py')[0],400)
