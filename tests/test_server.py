import base64
import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from server import Handler


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def call(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        conn.request(method, path, body, headers or {})
        result = conn.getresponse()
        status, response_headers, data = result.status, dict(result.getheaders()), result.read()
        conn.close()
        return status, response_headers, data

    def test_static_allowlist_and_headers(self):
        status, headers, body = self.call('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn(b'Data Rescue Workbench', body)
        self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
        self.assertEqual(self.call('GET', '/rescue.py')[0], 404)

    def test_foreign_origin_host_and_non_json_blocked(self):
        self.assertEqual(self.call('GET', '/', headers={'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.call('POST', '/api/inspect', '{}', {'Content-Type': 'application/json', 'Origin': 'https://evil.example'})[0], 403)
        self.assertEqual(self.call('POST', '/api/inspect', '{}', {'Content-Type': 'text/plain'})[0], 403)

    def test_inspect_api_success_and_readable_errors(self):
        body = json.dumps({'source': {'name': 'a.tsv', 'base64': base64.b64encode(b'id\tcount\n001\t0').decode()}})
        status, _, data = self.call('POST', '/api/inspect', body, {'Content-Type': 'application/json'})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)['rows'], [['001', '0']])
        self.assertEqual(self.call('POST', '/api/inspect', '{broken', {'Content-Type': 'application/json'})[0], 400)
