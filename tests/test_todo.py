"""Tests for /todo task list helpers."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aira.tools import list_todos, todo_add, todo_done, todo_delete, todo_clear


class TestTodoList(unittest.TestCase):
    def test_add_list_done_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("aira.tools._todos_dir", Path(tmp)):
                r = todo_add("Buy milk", "test")
                self.assertTrue(r["success"])
                tid = r["item"]["id"]

                items = list_todos("test")
                self.assertEqual(len(items), 1)
                self.assertEqual(items[0]["text"], "Buy milk")

                self.assertTrue(todo_done(tid, "test")["success"])
                self.assertTrue(list_todos("test")[0]["done"])

                self.assertTrue(todo_delete(tid, "test")["success"])
                self.assertEqual(list_todos("test"), [])

    def test_clear_done_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("aira.tools._todos_dir", Path(tmp)):
                a = todo_add("open task", "p")["item"]["id"]
                b = todo_add("done task", "p")["item"]["id"]
                todo_done(b, "p")
                r = todo_clear("p", done_only=True)
                self.assertEqual(r["removed"], 1)
                items = list_todos("p")
                self.assertEqual(len(items), 1)
                self.assertEqual(items[0]["id"], a)


if __name__ == "__main__":
    unittest.main()
