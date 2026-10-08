"""Shipped text assets must decode strictly as UTF-8 on every local platform."""
import unittest
from pathlib import Path

class SourceEncoding(unittest.TestCase):
    def test_runtime_text_assets_are_utf8(self):
        root=Path(__file__).resolve().parents[1]
        files=list((root/'web').glob('*'))+list(root.glob('*.py'))
        for path in files:
            if path.suffix in {'.py','.mjs','.js','.css','.html','.json','.webmanifest','.svg'}:
                with self.subTest(path=path.name):
                    path.read_bytes().decode('utf-8',errors='strict')
