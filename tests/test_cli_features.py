"""Tests for next-gen CLI features: diff parsing, hunk apply, checkpoints."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aira.tools import parse_diff, apply_diff_hunk, apply_hunk, save_checkpoint, restore_checkpoint


SAMPLE_DIFF = """--- a/example.py
+++ b/example.py
@@ -1,3 +1,4 @@
 line one
-line two
+line two modified
 line three
+line four
"""


class TestParseDiff(unittest.TestCase):
    def test_parses_hunks_and_file(self):
        hunks = parse_diff(SAMPLE_DIFF)
        self.assertEqual(len(hunks), 1)
        hunk = hunks[0]
        self.assertEqual(hunk["file"], "example.py")
        self.assertEqual(hunk["old_start"], 1)
        self.assertEqual(hunk["new_start"], 1)
        self.assertTrue(any(l.startswith("-") for l in hunk["lines"]))
        self.assertTrue(any(l.startswith("+") for l in hunk["lines"]))

    def test_multiple_hunks(self):
        diff = SAMPLE_DIFF + "\n@@ -10,2 +10,2 @@\n old\n+new\n"
        hunks = parse_diff(diff)
        self.assertEqual(len(hunks), 2)


class TestApplyDiffHunk(unittest.TestCase):
    def test_apply_single_hunk(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp = Path(tmp) / "example.py"
            fp.write_text("line one\nline two\nline three\n", encoding="utf-8")
            hunks = parse_diff(SAMPLE_DIFF)
            result = apply_diff_hunk(str(fp), hunks[0])
            self.assertTrue(result["success"])
            content = fp.read_text(encoding="utf-8")
            self.assertIn("line two modified", content)
            self.assertIn("line four", content)
            self.assertNotIn("line two\n", content)

    def test_apply_hunk_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp = Path(tmp) / "example.py"
            fp.write_text("alpha\nbeta\n", encoding="utf-8")
            diff = """--- a/example.py
+++ b/example.py
@@ -1,2 +1,2 @@
 alpha
-beta
+beta2
"""
            hunks = parse_diff(diff)
            result = apply_hunk(str(fp), hunks[0])
            self.assertTrue(result["success"])
            self.assertEqual(fp.read_text(encoding="utf-8"), "alpha\nbeta2\n")


class TestCheckpointRollback(unittest.TestCase):
    def test_save_and_restore_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            test_file = tmp_path / "state.txt"
            test_file.write_text("original", encoding="utf-8")
            conversation = [{"role": "user", "content": "hello"}]

            with patch("aira.tools.Path.cwd", return_value=tmp_path), patch(
                "aira.tools._checkpoint_dir", tmp_path / "checkpoints"
            ):
                ts = save_checkpoint(conversation)
                test_file.write_text("modified", encoding="utf-8")
                self.assertEqual(test_file.read_text(encoding="utf-8"), "modified")

                result = restore_checkpoint(ts)
                self.assertTrue(result["success"])
                self.assertEqual(test_file.read_text(encoding="utf-8"), "original")
                self.assertEqual(result["conversation"], conversation)


if __name__ == "__main__":
    unittest.main()
