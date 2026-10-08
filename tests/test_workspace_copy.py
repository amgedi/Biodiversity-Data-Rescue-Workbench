import hashlib, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from scripts.dev.copy_workspace import copy_workspace
from workspace_lock import WorkspaceLock

class WorkspaceCopy(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.source=Path(self.temp.name)/'source';self.source.mkdir();self.target=Path(self.temp.name)/'destination'
        (self.source/'originals').mkdir();(self.source/'originals/source.bin').write_bytes(b'001,NA,0\r\nexact original\x00')
    def tearDown(self):self.temp.cleanup()
    def test_preview_copies_nothing_and_copy_preserves_exact_source(self):
        before=(self.source/'originals/source.bin').read_bytes()
        self.assertFalse(copy_workspace(self.source,self.target)['copyPerformed']);self.assertFalse(self.target.exists())
        report=copy_workspace(self.source,self.target,True)
        self.assertTrue(Path(report['backup']).exists());self.assertEqual((self.target/'originals/source.bin').read_bytes(),before);self.assertEqual((self.source/'originals/source.bin').read_bytes(),before)
    def test_running_workspace_existing_target_and_overlap_rejected(self):
        with WorkspaceLock(self.source):
            with self.assertRaises(ValueError):copy_workspace(self.source,self.target,True)
        self.target.mkdir()
        with self.assertRaises(ValueError):copy_workspace(self.source,self.target,True)
        with self.assertRaises(ValueError):copy_workspace(self.source,self.source/'nested',True)
    def test_interrupted_copy_keeps_source_backup_and_no_destination(self):
        with patch('scripts.dev.copy_workspace.shutil.copy2',side_effect=OSError('Fictional write failure')):
            with self.assertRaises(OSError):copy_workspace(self.source,self.target,True)
        self.assertFalse(self.target.exists());self.assertTrue((self.source/'originals/source.bin').exists());self.assertEqual(len(list(Path(self.temp.name).glob('pre-copy-*.zip'))),1)
