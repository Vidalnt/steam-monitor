"""Unit tests for the monitor tools (no network). Run: python3 -m unittest discover -s tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from check_patterns import load_patterns, parse_sig, scan  # noqa: E402
from fetch_client import parse_manifest, select_packages  # noqa: E402
from publish import append_hash  # noqa: E402

HERE = Path(__file__).resolve().parent


class ManifestTest(unittest.TestCase):
    SAMPLE = (
        '"version"\t\t"1791918634"\n'
        '\t"bins_ubuntu12"\n\t{\n\t\t"file"\t\t"bins_ubuntu12.zip.abc123"\n\t}\n'
        '\t"strings_all"\n\t{\n\t\t"file"\t\t"strings_all.zip.def456"\n\t}\n'
    )

    def test_version_and_bins_first(self):
        version, pkgs = parse_manifest(self.SAMPLE)
        self.assertEqual(version, "1791918634")
        self.assertEqual(select_packages(pkgs)[0], "bins_ubuntu12.zip.abc123")

    def test_no_version_raises(self):
        with self.assertRaises(ValueError):
            parse_manifest('"ostype"\t\t"ubuntu12"\n')


class SigTest(unittest.TestCase):
    def test_wildcards(self):
        b, m = parse_sig("55 89 E5 ? ??")
        self.assertEqual(m, bytes([1, 1, 1, 0, 0]))
        data = bytes([0x00, 0x55, 0x89, 0xE5, 0xAA, 0xBB])
        self.assertTrue(scan(data, b, m))
        data2 = bytes([0x00, 0x55, 0x89, 0xE6, 0xAA, 0xBB])
        self.assertFalse(scan(data2, b, m))

    def test_load_patterns_json(self):
        pats, skips = load_patterns(HERE.parent / "data" / "patterns.json")
        self.assertGreater(len(pats), 10)
        names = [n for n, _, _ in pats]
        self.assertIn("CUserAppManager::BuildDepotDependency", names)
        self.assertIn("CCMConnection::RecvPkt", skips)

    def test_snapshot_roundtrip(self):
        import tempfile

        cpp = (
            'Pattern_t Foo\n{\n\t"NS::Foo",\n\t"55 89 E5 ? ??",\n'
            "\tSigFollowMode::None\n};\n"
        )
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "patterns.cpp"
            p.write_text(cpp + '\t\t\tif (std::string(pattern->name) == "NS::Foo")\n')
            pats, skips = load_patterns(p)
        self.assertEqual(len(pats), 1)
        self.assertIn("NS::Foo", skips)


class PublishTest(unittest.TestCase):
    def test_append_new_and_sorted(self):
        text = "SafeModeHashes:\n  20260310103750:\n    - aaa #ubuntu12_32\n"
        out = append_hash(text, "1791918634", "bbb")
        self.assertIn("  1791918634:\n    - bbb #ubuntu12_32\n", out)
        # numeric-chronological order preserved for timestamp keys
        self.assertLess(out.index("1791918634"), out.index("20260310103750"))

    def test_idempotent(self):
        text = "SafeModeHashes:\n  1791918634:\n    - bbb #ubuntu12_32\n"
        self.assertEqual(append_hash(text, "1791918634", "bbb"), text)


if __name__ == "__main__":
    unittest.main()
