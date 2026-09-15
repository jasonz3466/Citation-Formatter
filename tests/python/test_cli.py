"""Checks for the installed QuickCite command."""

import unittest
from unittest.mock import patch

from citation_formatter import __version__
from citation_formatter.cli import build_parser, main


class TestCommandLine(unittest.TestCase):
    def test_parser_accepts_local_server_options(self):
        options = build_parser().parse_args(
            ["--host", "0.0.0.0", "--port", "5050", "--debug"]
        )
        self.assertEqual(options.host, "0.0.0.0")
        self.assertEqual(options.port, 5050)
        self.assertTrue(options.debug)

    def test_main_starts_the_flask_app(self):
        with patch("citation_formatter.cli.app.run") as run:
            main(["--host", "127.0.0.1", "--port", "5051"])
        run.assert_called_once_with(host="127.0.0.1", port=5051, debug=False)

    def test_package_has_a_release_version(self):
        self.assertEqual(__version__, "0.4.1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
