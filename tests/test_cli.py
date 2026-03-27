"""Tests for the CLI entry point."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from spotibox.cli import main


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Spotibox" in result.output
    assert "--client-id" in result.output
    assert "--client-secret" in result.output
    assert "--redirect-uri" in result.output
    assert "--debug" in result.output
    assert "--verbose" in result.output
