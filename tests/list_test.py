"""Tests for the list_transcripts API function."""


from digest import DigestAPI

from conftest import (
    make_user_message,
    make_assistant_message,
    write_transcript,
    mark_processed,
)


def describe_list_transcripts():
    """Tests for listing unprocessed transcripts."""

    def it_returns_empty_when_raw_dir_missing(api: DigestAPI):
        """No raw directory means nothing to process."""
        result = api.list_transcripts()
        assert result == []

    def it_returns_empty_when_no_transcripts(api: DigestAPI, raw_dir):
        """Empty raw directory means nothing to process."""
        result = api.list_transcripts()
        assert result == []

    def it_returns_empty_when_all_fully_processed(api: DigestAPI, raw_dir, processed_dir):
        """All transcripts fully processed means nothing new."""
        messages = [
            make_user_message("Hello"),
            make_assistant_message("Hi there"),
            make_user_message("Goodbye"),
        ]
        write_transcript(raw_dir / "session-1.jsonl", messages)
        mark_processed(processed_dir, "session-1", 3)

        result = api.list_transcripts()
        assert result == []

    def it_lists_new_transcripts(api: DigestAPI, raw_dir, processed_dir):
        """New transcripts (no processed state) are listed."""
        messages = [
            make_user_message("Hello"),
            make_assistant_message("Hi"),
        ]
        write_transcript(raw_dir / "new-session.jsonl", messages)

        result = api.list_transcripts()

        assert len(result) == 1
        assert result[0].session_id == "new-session"
        assert result[0].processed_lines == 0
        assert result[0].total_lines == 2
        assert result[0].new_lines == 2
        assert result[0].has_new_content is True

    def it_lists_partially_processed_transcripts(api: DigestAPI, raw_dir, processed_dir):
        """Partially processed transcripts show remaining lines."""
        messages = [make_user_message(f"Line {i}") for i in range(5)]
        write_transcript(raw_dir / "partial.jsonl", messages)
        mark_processed(processed_dir, "partial", 2)

        result = api.list_transcripts()

        assert len(result) == 1
        assert result[0].session_id == "partial"
        assert result[0].processed_lines == 2
        assert result[0].total_lines == 5
        assert result[0].new_lines == 3

    def it_lists_multiple_transcripts_sorted(api: DigestAPI, raw_dir, processed_dir):
        """Multiple transcripts are listed in sorted order."""
        write_transcript(raw_dir / "zebra.jsonl", [make_user_message("Z")])
        write_transcript(raw_dir / "alpha.jsonl", [make_user_message("A")])
        write_transcript(raw_dir / "beta.jsonl", [make_user_message("B")])

        result = api.list_transcripts()

        assert len(result) == 3
        assert result[0].session_id == "alpha"
        assert result[1].session_id == "beta"
        assert result[2].session_id == "zebra"

    def it_ignores_non_jsonl_files(api: DigestAPI, raw_dir, processed_dir):
        """Only .jsonl files are considered."""
        write_transcript(raw_dir / "real.jsonl", [make_user_message("Real")])
        (raw_dir / "fake.txt").write_text("Not a transcript")
        (raw_dir / "fake.json").write_text("{}")

        result = api.list_transcripts()

        assert len(result) == 1
        assert result[0].session_id == "real"
