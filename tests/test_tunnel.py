"""Tests for public web tunnel helpers."""

import unittest
from unittest.mock import patch

from aira.tools import list_tunnel_providers, stop_web_tunnel


class TestTunnelProviders(unittest.TestCase):
    def test_list_tunnel_providers_returns_list(self):
        with patch("shutil.which", return_value=None):
            self.assertEqual(list_tunnel_providers(), [])

    def test_stop_tunnel_when_none_running(self):
        stop_web_tunnel()
        r = stop_web_tunnel()
        self.assertFalse(r["success"])


if __name__ == "__main__":
    unittest.main()
