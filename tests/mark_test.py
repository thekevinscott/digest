"""Tests for the mark_processed API function."""

import json
import pytest

from digest import DigestAPI
from conftest import (
    make_user_message,
    write_transcript,
    mark_processed as fixture_mark_processed,
)


def describe_mark_processed():
    """Tests for marking transcripts as processed."""

    def it_creates_processed_json_with_line_number(api: DigestAPI, raw_dir, processed_dir):
        """Creates processed file with correct line count."""
        messages = [
            make_user_message("Line 1"),
            make_user_message("Line 2"),
            make_user_message("Line 3"),
        ]
        write_transcript(raw_dir / "test.jsonl", messages)

        result = api.mark_processed("test")

        assert result.session_id == "test"
        assert result.lines_marked == 3

        processed_file = processed_dir / "test.json"
        assert processed_file.exists()
        data = json.loads(processed_file.read_text())
        assert data["lineNumber"] == 3

    def it_updates_existing_processed_file(api: DigestAPI, raw_dir, processed_dir):
        """Updates existing processed file to new line count."""
        messages = [make_user_message(f"Line {i}") for i in range(5)]
        write_transcript(raw_dir / "update.jsonl", messages)

        # Mark initial state
        fixture_mark_processed(processed_dir, "update", 2)

        # Re-mark with new state
        result = api.mark_processed("update")

        assert result.lines_marked == 5
        data = json.loads((processed_dir / "update.json").read_text())
        assert data["lineNumber"] == 5

    def it_creates_processed_directory_if_missing(api: DigestAPI, raw_dir, temp_cwd):
        """Creates processed directory if it doesn't exist."""
        messages = [make_user_message("Test")]
        write_transcript(raw_dir / "new.jsonl", messages)

        # Remove processed dir if it exists
        processed_path = temp_cwd / "notes" / "logs" / "processed"
        if processed_path.exists():
            processed_path.rmdir()

        result = api.mark_processed("new")

        assert result.lines_marked == 1
        assert (processed_path / "new.json").exists()

    def it_raises_on_missing_transcript(api: DigestAPI, raw_dir, processed_dir):
        """Raises FileNotFoundError for non-existent transcript."""
        with pytest.raises(FileNotFoundError):
            api.mark_processed("nonexistent")

    def it_handles_empty_transcript(api: DigestAPI, raw_dir, processed_dir):
        """Empty transcript file gets marked with 0 lines."""
        (raw_dir / "empty.jsonl").write_text("")

        result = api.mark_processed("empty")

        assert result.lines_marked == 0
        data = json.loads((processed_dir / "empty.json").read_text())
        assert data["lineNumber"] == 0

    def it_handles_large_transcript(api: DigestAPI, raw_dir, processed_dir):
        """Large transcript file line count is accurate."""
        messages = [make_user_message(f"Line {i}") for i in range(10_000)]
        write_transcript(raw_dir / "large.jsonl", messages)

        result = api.mark_processed("large")

        assert result.lines_marked == 10_000
