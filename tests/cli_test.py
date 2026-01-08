"""Tests for the CLI module."""

import subprocess
import sys
from pathlib import Path

import pytest

from conftest import make_user_message, write_transcript


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run the digest CLI with given arguments."""
    cmd = [sys.executable, "-m", "digest", *args]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


def describe_path_argument():
    """Tests for --path argument."""

    def it_list_uses_path_argument(tmp_path):
        """--list respects --path argument."""
        # Set up notes structure in tmp_path
        raw_dir = tmp_path / "notes" / "logs" / "raw"
        raw_dir.mkdir(parents=True)
        write_transcript(raw_dir / "test-session.jsonl", [make_user_message("Hello")])

        result = run_cli("--path", str(tmp_path), "--list")

        assert result.returncode == 0
        assert "test-session" in result.stdout
        assert "1" in result.stdout  # 1 line

    def it_extract_uses_path_argument(tmp_path):
        """--extract respects --path argument."""
        raw_dir = tmp_path / "notes" / "logs" / "raw"
        raw_dir.mkdir(parents=True)
        write_transcript(raw_dir / "session-1.jsonl", [make_user_message("Test content")])

        result = run_cli("--path", str(tmp_path), "--extract", "session-1")

        assert result.returncode == 0
        assert "[USER]: Test content" in result.stdout

    def it_mark_uses_path_argument(tmp_path):
        """--mark respects --path argument."""
        raw_dir = tmp_path / "notes" / "logs" / "raw"
        processed_dir = tmp_path / "notes" / "logs" / "processed"
        raw_dir.mkdir(parents=True)
        processed_dir.mkdir(parents=True)
        write_transcript(raw_dir / "mark-test.jsonl", [make_user_message("Content")])

        result = run_cli("--path", str(tmp_path), "--mark", "mark-test")

        assert result.returncode == 0
        assert "Marked mark-test as processed" in result.stdout
        assert (processed_dir / "mark-test.json").exists()

    def it_defaults_to_cwd_when_path_not_specified(tmp_path):
        """Without --path, uses current working directory."""
        raw_dir = tmp_path / "notes" / "logs" / "raw"
        raw_dir.mkdir(parents=True)
        write_transcript(raw_dir / "cwd-test.jsonl", [make_user_message("CWD content")])

        result = run_cli("--list", cwd=tmp_path)

        assert result.returncode == 0
        assert "cwd-test" in result.stdout

    def it_path_can_be_relative(tmp_path):
        """--path accepts relative paths."""
        notes_dir = tmp_path / "subdir" / "notes" / "logs" / "raw"
        notes_dir.mkdir(parents=True)
        write_transcript(notes_dir / "rel-test.jsonl", [make_user_message("Relative")])

        result = run_cli("--path", "subdir", "--list", cwd=tmp_path)

        assert result.returncode == 0
        assert "rel-test" in result.stdout

    def it_path_errors_gracefully_when_no_transcripts(tmp_path):
        """--path to empty directory shows 'Nothing new'."""
        (tmp_path / "notes" / "logs" / "raw").mkdir(parents=True)

        result = run_cli("--path", str(tmp_path), "--list")

        assert result.returncode == 0
        assert "Nothing new to process" in result.stdout

    def it_extract_errors_when_session_not_found(tmp_path):
        """--extract with nonexistent session ID errors."""
        (tmp_path / "notes" / "logs" / "raw").mkdir(parents=True)

        result = run_cli("--path", str(tmp_path), "--extract", "nonexistent")

        assert result.returncode == 1
        assert "not found" in result.stderr.lower()
