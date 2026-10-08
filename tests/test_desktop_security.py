"""Desktop launch credentials must not bypass loopback and edit authority checks."""
import http.client, json, tempfile, threading, unittest
from server import Handler, LocalServer
from storage import Store
from large_data import LargeStore

class DesktopSecurity(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.server=LocalServer(('127.0.0.1',0),Handler)
        self.server.store=Store(self.temp.name);self.server.large=LargeStore(self.server.store.root/'large')
        self.server.auth_token='a'*48;self.server.desktop=True
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
    def request(self,path,headers=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        connection.request('GET',path,headers=headers or {})
        response=connection.getresponse();result=(response.status,dict(response.getheaders()),response.read());connection.close();return result
    def test_unauthorized_static_and_api_requests_rejected(self):
        self.assertEqual(self.request('/')[0],403)
        self.assertEqual(self.request('/api/project-hub')[0],403)
        self.assertEqual(self.request('/api/workspace',{'X-Workbench-Token':'wrong'})[0],403)
    def test_bootstrap_cookie_and_authorized_health(self):
        status,headers,_=self.request('/desktop/'+self.server.auth_token)
        self.assertEqual(status,303);self.assertIn('HttpOnly',headers['Set-Cookie']);self.assertIn('SameSite=Strict',headers['Set-Cookie'])
        status,_,body=self.request('/api/workspace',{'Cookie':headers['Set-Cookie'].split(';')[0]})
        self.assertEqual(status,200);self.assertTrue(json.loads(body)['desktop'])
    def test_credential_never_overrides_host_or_origin(self):
        for headers in [{'Host':'evil.example'},{'Origin':'https://evil.example'}]:
            headers['X-Workbench-Token']=self.server.auth_token
            self.assertEqual(self.request('/api/workspace',headers)[0],403)
        self.assertEqual(self.request('/desktop/'+self.server.auth_token,{'Origin':'https://evil.example'})[0],403)
    def test_incorrect_bootstrap_does_not_set_cookie(self):
        status,headers,_=self.request('/desktop/wrong')
        self.assertEqual(status,403);self.assertNotIn('Set-Cookie',headers)
