import unittest
from scripts.build.workbench import validate_release_acceptance

class V7ReleaseGate(unittest.TestCase):
    def record(self):
        return {'sourceFingerprint':'exact-source','featureParityComplete':True,'desktopAcceptance':True,'launcherAccepted':True,'helpTutorialParity':True,'packagedVisualIterations':3}
    def test_missing_or_stale_acceptance_cannot_publish(self):
        self.assertFalse(validate_release_acceptance(None,'exact-source'))
        self.assertFalse(validate_release_acceptance(self.record(),'changed-source'))
    def test_browser_iterations_and_partial_parity_are_not_native_acceptance(self):
        record=self.record();record['packagedVisualIterations']=0
        self.assertFalse(validate_release_acceptance(record,'exact-source'))
        record=self.record();record['featureParityComplete']=False
        self.assertFalse(validate_release_acceptance(record,'exact-source'))
    def test_strict_matching_acceptance_is_required(self):
        self.assertTrue(validate_release_acceptance(self.record(),'exact-source'))
        record=self.record();record['desktopAcceptance']='true'
        self.assertFalse(validate_release_acceptance(record,'exact-source'))
