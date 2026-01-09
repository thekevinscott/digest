"""Tests for the CLI module."""

import subprocess
import sys
from pathlib import Path

import pytest

from conftest import make_user_message, write_transcript


def run_cli(*args: str, cwd: Path | None = None, input: str | None = None) -> subprocess.CompletedProcess:
    """Run the digest CLI with given arguments."""
    cmd = [sys.executable, "-m", "digest", *args]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, input=input)


def describe_subcommands():
    """Tests for subcommand-based CLI structure."""

    def it_list_subcommand_shows_transcripts(tmp_path):
        """list subcommand shows transcripts."""
        raw_dir = tmp_path / "notes" / "logs" / "raw"
        raw_dir.mkdir(parents=True)
        write_transcript(raw_dir / "test-session.jsonl", [make_user_message("Hello")])

        result = run_cli("--path", str(tmp_path), "list")

        assert result.returncode == 0
        assert "test-session" in result.stdout

    def it_extract_subcommand_extracts_content(tmp_path):
        """extract subcommand extracts content."""
        raw_dir = tmp_path / "notes" / "logs" / "raw"
        raw_dir.mkdir(parents=True)
        write_transcript(raw_dir / "session-1.jsonl", [make_user_message("Test content")])

        result = run_cli("--path", str(tmp_path), "extract", "session-1")

        assert result.returncode == 0
        assert "[USER]: Test content" in result.stdout

    def it_mark_subcommand_marks_processed(tmp_path):
        """mark subcommand marks transcript as processed."""
        raw_dir = tmp_path / "notes" / "logs" / "raw"
        processed_dir = tmp_path / "notes" / "logs" / "processed"
        raw_dir.mkdir(parents=True)
        processed_dir.mkdir(parents=True)
        write_transcript(raw_dir / "mark-test.jsonl", [make_user_message("Content")])

        result = run_cli("--path", str(tmp_path), "mark", "mark-test")

        assert result.returncode == 0
        assert "Marked mark-test as processed" in result.stdout
        assert (processed_dir / "mark-test.json").exists()

    def it_defaults_to_list_when_no_subcommand(tmp_path):
        """No subcommand defaults to list."""
        raw_dir = tmp_path / "notes" / "logs" / "raw"
        raw_dir.mkdir(parents=True)
        write_transcript(raw_dir / "default-test.jsonl", [make_user_message("Default")])

        result = run_cli("--path", str(tmp_path))

        assert result.returncode == 0
        assert "default-test" in result.stdout

    def it_path_works_with_all_subcommands(tmp_path):
        """--path argument works with all subcommands."""
        raw_dir = tmp_path / "notes" / "logs" / "raw"
        raw_dir.mkdir(parents=True)
        write_transcript(raw_dir / "path-test.jsonl", [make_user_message("Path test")])

        # list
        result = run_cli("--path", str(tmp_path), "list")
        assert result.returncode == 0
        assert "path-test" in result.stdout


def describe_note_command():
    """Tests for note subcommand."""

    def it_creates_file_with_timestamp(tmp_path):
        """note creates file with timestamp header."""
        result = run_cli(
            "--path", str(tmp_path),
            "note", "notes/digest/test.md",
            "- Test item"
        )

        assert result.returncode == 0
        assert "Added 1 lines" in result.stdout

        content = (tmp_path / "notes" / "digest" / "test.md").read_text()
        assert "---" in content
        assert "### 20" in content  # Timestamp starts with year
        assert "- Test item" in content

    def it_prepends_to_existing_file(tmp_path):
        """note prepends new entry to existing file."""
        digest_dir = tmp_path / "notes" / "digest"
        digest_dir.mkdir(parents=True)
        test_file = digest_dir / "existing.md"
        test_file.write_text("---\n### 2026-01-01 00:00\n\n- Old item\n")

        result = run_cli(
            "--path", str(tmp_path),
            "note", "notes/digest/existing.md",
            "- New item"
        )

        assert result.returncode == 0
        content = test_file.read_text()
        # New entry should be at the top
        assert content.index("- New item") < content.index("- Old item")

    def it_adds_project_header(tmp_path):
        """note adds project header when --project specified."""
        result = run_cli(
            "--path", str(tmp_path),
            "note", "notes/digest/proj.md",
            "--project", "my-project",
            "- Project item"
        )

        assert result.returncode == 0
        content = (tmp_path / "notes" / "digest" / "proj.md").read_text()
        assert "## my-project" in content

    def it_reads_from_stdin(tmp_path):
        """note reads text from stdin when not provided as argument."""
        result = run_cli(
            "--path", str(tmp_path),
            "note", "notes/digest/stdin.md",
            input="- Item from stdin\n- Another item"
        )

        assert result.returncode == 0
        assert "Added 2 lines" in result.stdout
        content = (tmp_path / "notes" / "digest" / "stdin.md").read_text()
        assert "- Item from stdin" in content
        assert "- Another item" in content

    def it_preserves_inline_source_refs(tmp_path):
        """note preserves inline source references."""
        result = run_cli(
            "--path", str(tmp_path),
            "note", "notes/digest/refs.md",
            "- Insight here [abc123:42]"
        )

        assert result.returncode == 0
        content = (tmp_path / "notes" / "digest" / "refs.md").read_text()
        assert "[abc123:42]" in content

    def it_errors_on_empty_text(tmp_path):
        """note errors when text is empty."""
        result = run_cli(
            "--path", str(tmp_path),
            "note", "notes/digest/empty.md",
            ""
        )

        assert result.returncode == 1
        assert "empty" in result.stderr.lower()

    def it_uses_system_date_for_timestamp(tmp_path):
        """note uses system date command for timestamp."""
        import subprocess as sp
        expected_date = sp.run(["date", "+%Y-%m-%d"], capture_output=True, text=True).stdout.strip()

        result = run_cli(
            "--path", str(tmp_path),
            "note", "notes/digest/date.md",
            "- Date test"
        )

        assert result.returncode == 0
        content = (tmp_path / "notes" / "digest" / "date.md").read_text()
        assert expected_date in content
