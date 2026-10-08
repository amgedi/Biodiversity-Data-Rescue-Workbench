import unittest
from edit_sessions import EditSessions

class EditingAuthorityTests(unittest.TestCase):
    def setUp(self):self.time=0;self.sessions=EditSessions(clock=lambda:self.time,ttl=45)
    def claim(self,pid='a',session='window-one'):return self.sessions.claim(pid,session)
    def test_second_window_read_only_does_not_receive_token(self):
        first=self.claim();second=self.claim(session='window-two');self.assertTrue(first['editing']);self.assertFalse(second['editing']);self.assertNotIn('token',second)
    def test_takeover_rejects_previous_window_even_at_same_scientific_revision(self):
        first=self.claim();second=self.sessions.claim('a','window-two',True,first['generation']);self.sessions.check('a','window-two',second['token'])
        with self.assertRaisesRegex(ValueError,'AUTHORITY_LOST'):self.sessions.check('a','window-one',first['token'])
    def test_reviewed_takeover_generation_cannot_overwrite_new_owner(self):
        first=self.claim();self.sessions.claim('a','window-two',True,first['generation'])
        with self.assertRaisesRegex(ValueError,'TAKEOVER_CONFLICT'):self.sessions.claim('a','window-three',True,first['generation'])
    def test_expired_editor_cannot_write_and_can_explicitly_reacquire(self):
        first=self.claim();self.time=46
        with self.assertRaisesRegex(ValueError,'EXPIRED'):self.sessions.check('a','window-one',first['token'])
        second=self.claim(session='window-two');self.assertGreater(second['generation'],first['generation'])
    def test_different_projects_have_independent_authority(self):
        a=self.claim();b=self.claim('b','window-two');self.sessions.check('a','window-one',a['token']);self.sessions.check('b','window-two',b['token'])
    def test_anonymous_client_cannot_bypass_live_editor(self):
        self.claim()
        with self.assertRaisesRegex(ValueError,'AUTHORITY_LOST'):self.sessions.check('a')
