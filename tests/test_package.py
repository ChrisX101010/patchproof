import importlib.util
from pathlib import Path
import unittest
import zipfile


class PortablePackageTests(unittest.TestCase):
    def test_archive_has_platform_independent_metadata_and_no_compressor_dependency(self):
        root = Path(__file__).resolve().parent.parent
        spec = importlib.util.spec_from_file_location('package_tool', root / 'tools/package.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        archive, _ = module.package()
        with zipfile.ZipFile(archive) as bundle:
            for item in bundle.infolist():
                with self.subTest(file=item.filename):
                    self.assertEqual(item.compress_type, zipfile.ZIP_STORED)
                    self.assertEqual(item.create_system, 3)
                    self.assertEqual(item.date_time, (2026, 1, 1, 0, 0, 0))
