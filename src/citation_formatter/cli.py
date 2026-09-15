"""Command-line entry point for the local QuickCite server."""

import argparse
import os

from . import __version__
from .app import app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quickcite",
        description="Run the QuickCite citation formatter.",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("HOST", "127.0.0.1"),
        help="Address to listen on. Defaults to 127.0.0.1.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=os.environ.get("PORT", "5000"),
        help="Port to listen on. Defaults to 5000.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Flask's local debugger and automatic reload.",
    )
    parser.add_argument("--version", action="version", version=f"QuickCite {__version__}")
    return parser


def main(argv: list[str] | None = None) -> None:
    """Start the local server using command-line or environment settings."""
    options = build_parser().parse_args(argv)
    app.run(host=options.host, port=options.port, debug=options.debug)
