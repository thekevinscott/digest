"""Integration tests for the dream skill.

These tests exercise the full workflow across list, extract, and mark operations.
"""

import json
import pytest

from digest import DigestAPI
from conftest import (
    make_user_message,
    make_assistant_message,
    make_tool_use,
    make_tool_result,
    write_transcript,
    append_to_transcript,
    mark_processed as fixture_mark_processed,
)


def describe_empty_state():
    """Tests for fresh/empty state."""

    def it_handles_fresh_directory(api: DigestAPI):
        """Fresh directory with no transcripts."""
        result = api.list_transcripts()
        assert result == []

    def it_extract_errors_gracefully_for_nonexistent(api: DigestAPI):
        """Extract on nonexistent session raises error."""
        with pytest.raises(FileNotFoundError):
            api.extract("nonexistent")


def describe_single_transcript():
    """Tests for single transcript workflow."""

    def it_new_transcript_appears_in_list(api: DigestAPI, raw_dir, processed_dir):
        """New transcript shows in list."""
        write_transcript(
            raw_dir / "session-1.jsonl",
            [make_user_message("Hello"), make_assistant_message("Hi")],
        )

        result = api.list_transcripts()

        assert len(result) == 1
        assert result[0].session_id == "session-1"
        assert result[0].processed_lines == 0
        assert result[0].total_lines == 2

    def it_extract_returns_all_content(api: DigestAPI, raw_dir, processed_dir):
        """Extract returns full content for small transcript."""
        write_transcript(
            raw_dir / "session-1.jsonl",
            [
                make_user_message("Hello"),
                make_assistant_message("Hi there"),
                make_user_message("Thanks"),
            ],
        )

        result = api.extract("session-1")

        assert len(result.content) == 3
        assert "[USER]: Hello" in result.content[0]
        assert "[ASSISTANT]: Hi there" in result.content[1]
        assert "[USER]: Thanks" in result.content[2]
        assert result.next_cursor is None

    def it_mark_updates_state(api: DigestAPI, raw_dir, processed_dir):
        """Mark updates processed state."""
        write_transcript(
            raw_dir / "session-1.jsonl",
            [make_user_message("Test")],
        )

        result = api.mark_processed("session-1")

        assert result.lines_marked == 1
        assert (processed_dir / "session-1.json").exists()

    def it_list_shows_nothing_after_mark(api: DigestAPI, raw_dir, processed_dir):
        """List shows nothing new after mark."""
        write_transcript(
            raw_dir / "session-1.jsonl",
            [make_user_message("Test")],
        )
        api.mark_processed("session-1")

        result = api.list_transcripts()

        assert result == []

    def it_new_lines_show_after_append(api: DigestAPI, raw_dir, processed_dir):
        """Appended lines show as new content."""
        path = raw_dir / "session-1.jsonl"
        write_transcript(path, [make_user_message("Original")])
        api.mark_processed("session-1")

        append_to_transcript(path, [make_user_message("Appended")])

        result = api.list_transcripts()

        assert len(result) == 1
        assert result[0].processed_lines == 1
        assert result[0].total_lines == 2
        assert result[0].new_lines == 1

    def it_extract_from_cursor_gets_only_new(api: DigestAPI, raw_dir, processed_dir):
        """Extract from cursor skips already processed content."""
        path = raw_dir / "session-1.jsonl"
        write_transcript(
            path,
            [make_user_message("Old 1"), make_user_message("Old 2")],
        )
        fixture_mark_processed(processed_dir, "session-1", 2)

        append_to_transcript(path, [make_user_message("New")])

        result = api.extract("session-1")  # Should default to line 3

        assert result.start_line == 3
        assert len(result.content) == 1
        assert "New" in result.content[0]


def describe_multiple_transcripts():
    """Tests for multiple transcript handling."""

    def it_lists_all_new_transcripts(api: DigestAPI, raw_dir, processed_dir):
        """Multiple new transcripts all appear in list."""
        write_transcript(raw_dir / "alpha.jsonl", [make_user_message("A")])
        write_transcript(raw_dir / "beta.jsonl", [make_user_message("B")])
        write_transcript(raw_dir / "gamma.jsonl", [make_user_message("G")])

        result = api.list_transcripts()

        assert len(result) == 3
        session_ids = [t.session_id for t in result]
        assert "alpha" in session_ids
        assert "beta" in session_ids
        assert "gamma" in session_ids

    def it_extracts_each_independently(api: DigestAPI, raw_dir, processed_dir):
        """Each transcript can be extracted independently."""
        write_transcript(raw_dir / "first.jsonl", [make_user_message("First content")])
        write_transcript(raw_dir / "second.jsonl", [make_user_message("Second content")])

        first_result = api.extract("first")
        second_result = api.extract("second")

        assert "First content" in first_result.content[0]
        assert "Second content" in second_result.content[0]

    def it_marking_one_doesnt_affect_others(api: DigestAPI, raw_dir, processed_dir):
        """Marking one transcript doesn't affect others."""
        write_transcript(raw_dir / "keep.jsonl", [make_user_message("Keep")])
        write_transcript(raw_dir / "mark.jsonl", [make_user_message("Mark")])

        api.mark_processed("mark")

        result = api.list_transcripts()

        assert len(result) == 1
        assert result[0].session_id == "keep"

    def it_handles_mixed_processing_states(api: DigestAPI, raw_dir, processed_dir):
        """Handles transcripts in different processing states."""
        # Fully processed
        write_transcript(raw_dir / "done.jsonl", [make_user_message("Done")])
        fixture_mark_processed(processed_dir, "done", 1)

        # Partially processed
        write_transcript(
            raw_dir / "partial.jsonl",
            [make_user_message("P1"), make_user_message("P2"), make_user_message("P3")],
        )
        fixture_mark_processed(processed_dir, "partial", 1)

        # New
        write_transcript(raw_dir / "new.jsonl", [make_user_message("New")])

        result = api.list_transcripts()

        assert len(result) == 2
        session_ids = {t.session_id for t in result}
        assert "done" not in session_ids
        assert "partial" in session_ids
        assert "new" in session_ids


def describe_pagination():
    """Tests for pagination through large transcripts."""

    def it_requires_multiple_calls_for_large_transcript(api: DigestAPI, raw_dir, processed_dir):
        """Large transcript requires multiple extract calls."""
        messages = [make_user_message(f"Message {i}" + "x" * 500) for i in range(100)]
        write_transcript(raw_dir / "large.jsonl", messages)

        result = api.extract("large", char_budget=10_000)

        assert result.next_cursor is not None
        assert result.total_lines == 100

    def it_cursor_chain_reaches_end(api: DigestAPI, raw_dir, processed_dir):
        """Following cursor chain eventually reaches end."""
        messages = [make_user_message(f"Msg {i}") for i in range(50)]
        write_transcript(raw_dir / "chain.jsonl", messages)

        cursor = 1
        all_content = []
        iterations = 0

        while iterations < 100:
            result = api.extract("chain", cursor=cursor, char_budget=1000)
            all_content.extend(result.content)

            if result.next_cursor is None:
                break

            cursor = result.next_cursor
            iterations += 1

        combined = "\n".join(all_content)
        assert result.next_cursor is None

        # Verify all messages were captured (accounting for overlap duplicates)
        for i in range(50):
            assert f"Msg {i}" in combined

    def it_overlap_ensures_no_gaps(api: DigestAPI, raw_dir, processed_dir):
        """Overlap ensures context continuity."""
        messages = [make_user_message(f"Unique{i:04d}") for i in range(30)]
        write_transcript(raw_dir / "overlap.jsonl", messages)

        seen = set()
        cursor = 1

        for _ in range(20):
            result = api.extract("overlap", cursor=cursor, char_budget=500)

            for content in result.content:
                for i in range(30):
                    if f"Unique{i:04d}" in content:
                        seen.add(i)

            if result.next_cursor is None:
                break

            cursor = result.next_cursor

        assert seen == set(range(30))

    def it_final_extract_has_no_cursor(api: DigestAPI, raw_dir, processed_dir):
        """Final extraction has next_cursor=None."""
        messages = [make_user_message("Only")]
        write_transcript(raw_dir / "final.jsonl", messages)

        result = api.extract("final")

        assert result.next_cursor is None


def describe_incremental_processing():
    """Tests for incremental/resume processing."""

    def it_resumes_from_partial_processing(api: DigestAPI, raw_dir, processed_dir):
        """Can resume processing after partial completion."""
        messages = [make_user_message(f"Line {i}") for i in range(20)]
        write_transcript(raw_dir / "resume.jsonl", messages)

        # Process first part
        result1 = api.extract("resume", cursor=1, char_budget=500)
        cursor = result1.next_cursor

        # Append more content
        append_to_transcript(
            raw_dir / "resume.jsonl",
            [make_user_message(f"New {i}") for i in range(5)],
        )

        # Resume from cursor - should see remaining + new
        result2 = api.extract("resume", cursor=cursor, char_budget=50_000)

        assert result2.total_lines == 25  # 20 original + 5 new


def describe_edge_cases():
    """Tests for edge cases and unusual inputs."""

    def it_handles_empty_transcript(api: DigestAPI, raw_dir, processed_dir):
        """Empty transcript file."""
        (raw_dir / "empty.jsonl").write_text("")

        result = api.list_transcripts()
        # Empty file has 0 lines, so nothing new
        assert result == []

    def it_handles_only_metadata_lines(api: DigestAPI, raw_dir, processed_dir):
        """Transcript with only non-user/assistant messages."""
        path = raw_dir / "meta.jsonl"
        with open(path, "w") as f:
            f.write('{"type": "system", "message": {"content": "sys"}}\n')
            f.write('{"type": "metadata", "data": {}}\n')

        result = api.extract("meta")

        assert result.content == []  # No user/assistant messages

    def it_handles_single_huge_message(api: DigestAPI, raw_dir, processed_dir):
        """Single message exceeding budget."""
        huge = "X" * 500_000  # 500KB
        write_transcript(raw_dir / "huge.jsonl", [make_user_message(huge)])

        result = api.extract("huge", char_budget=50_000)

        assert len(result.content) == 1
        assert huge in result.content[0]
        assert result.next_cursor is None

    def it_handles_unicode_emoji_content(api: DigestAPI, raw_dir, processed_dir):
        """Content with unicode and emoji."""
        messages = [
            make_user_message("Hello! How are you?"),
            make_assistant_message("I'm great! Here's some unicode: cafe"),
        ]
        write_transcript(raw_dir / "unicode.jsonl", messages)

        result = api.extract("unicode")

        content = "\n".join(result.content)
        assert "cafe" in content

    def it_skips_malformed_json_gracefully(api: DigestAPI, raw_dir, processed_dir):
        """Malformed JSON lines are skipped."""
        path = raw_dir / "malformed.jsonl"
        with open(path, "w") as f:
            f.write('{"type": "user", "message": {"content": "Good"}}\n')
            f.write("not json at all\n")
            f.write('{"broken json\n')
            f.write('{"type": "user", "message": {"content": "Also good"}}\n')

        result = api.extract("malformed")

        content = "\n".join(result.content)
        assert "Good" in content
        assert "Also good" in content

    def it_handles_cursor_beyond_file(api: DigestAPI, raw_dir, processed_dir):
        """Cursor beyond end of file."""
        write_transcript(raw_dir / "short.jsonl", [make_user_message("One")])

        result = api.extract("short", cursor=100)

        assert result.content == []
        assert result.next_cursor is None

    def it_handles_cursor_at_exact_end(api: DigestAPI, raw_dir, processed_dir):
        """Cursor at exact last line."""
        write_transcript(
            raw_dir / "exact.jsonl",
            [make_user_message("First"), make_user_message("Last")],
        )

        result = api.extract("exact", cursor=2)

        assert len(result.content) == 1
        assert "Last" in result.content[0]
        assert result.next_cursor is None

    def it_handles_processed_beyond_current_length(api: DigestAPI, raw_dir, processed_dir):
        """Processed state pointing beyond current file (truncated file)."""
        write_transcript(raw_dir / "truncated.jsonl", [make_user_message("Now short")])
        fixture_mark_processed(processed_dir, "truncated", 100)

        result = api.list_transcripts()

        # File is 1 line, processed is 100 - nothing new
        assert result == []


def describe_concurrent_scenarios():
    """Tests for concurrent-like scenarios."""

    def it_handles_content_appended_during_extraction(api: DigestAPI, raw_dir, processed_dir):
        """Content appended after read but before cursor use."""
        messages = [make_user_message(f"Original {i}") for i in range(10)]
        write_transcript(raw_dir / "append.jsonl", messages)

        result1 = api.extract("append", cursor=1, char_budget=500)

        # Append before next extraction
        append_to_transcript(
            raw_dir / "append.jsonl",
            [make_user_message("Appended")],
        )

        # Cursor is still valid
        result2 = api.extract("append", cursor=result1.next_cursor)

        assert result2.total_lines == 11

    def it_same_cursor_is_idempotent(api: DigestAPI, raw_dir, processed_dir):
        """Multiple extractions with same cursor return same content."""
        messages = [make_user_message(f"Msg {i}") for i in range(5)]
        write_transcript(raw_dir / "idem.jsonl", messages)

        result1 = api.extract("idem", cursor=2)
        result2 = api.extract("idem", cursor=2)

        assert result1.content == result2.content
        assert result1.next_cursor == result2.next_cursor


def describe_real_transcript_format():
    """Tests against actual Claude Code transcript structures."""

    def it_handles_complex_tool_use_input(api: DigestAPI, raw_dir, processed_dir):
        """Tool use with complex nested input."""
        msg = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Edit",
                        "input": {
                            "file_path": "/path/to/file.py",
                            "old_string": "def foo():\n    pass",
                            "new_string": "def foo():\n    return 42",
                        },
                    }
                ]
            },
        }
        path = raw_dir / "complex.jsonl"
        with open(path, "w") as f:
            f.write(json.dumps(msg) + "\n")

        result = api.extract("complex")

        content = result.content[0]
        assert "[TOOL USE: Edit]" in content
        assert "file_path" in content
        assert "old_string" in content

    def it_handles_tool_result_array_content(api: DigestAPI, raw_dir, processed_dir):
        """Tool result with array of text blocks."""
        msg = {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "content": [
                            {"type": "text", "text": "Line 1 of file"},
                            {"type": "text", "text": "Line 2 of file"},
                        ],
                    }
                ]
            },
        }
        path = raw_dir / "array.jsonl"
        with open(path, "w") as f:
            f.write(json.dumps(msg) + "\n")

        result = api.extract("array")

        content = result.content[0]
        assert "[TOOL RESULT]:" in content
        assert "Line 1 of file" in content
        assert "Line 2 of file" in content

    def it_handles_mixed_content_blocks(api: DigestAPI, raw_dir, processed_dir):
        """Message with multiple content block types."""
        msg = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "Let me check that file."},
                    {"type": "tool_use", "name": "Read", "input": {"file_path": "/x"}},
                    {"type": "text", "text": "And also this one."},
                    {"type": "tool_use", "name": "Read", "input": {"file_path": "/y"}},
                ]
            },
        }
        path = raw_dir / "mixed.jsonl"
        with open(path, "w") as f:
            f.write(json.dumps(msg) + "\n")

        result = api.extract("mixed")

        content = result.content[0]
        assert "Let me check that file" in content
        assert "[TOOL USE: Read]" in content
        assert "And also this one" in content

    def it_handles_empty_content_gracefully(api: DigestAPI, raw_dir, processed_dir):
        """Messages with empty or null content."""
        path = raw_dir / "empty-content.jsonl"
        with open(path, "w") as f:
            f.write('{"type": "user", "message": {"content": ""}}\n')
            f.write('{"type": "user", "message": {"content": null}}\n')
            f.write('{"type": "user", "message": {"content": []}}\n')
            f.write('{"type": "user", "message": {"content": "Real content"}}\n')

        result = api.extract("empty-content")

        # Only the "Real content" message should be extracted
        assert len(result.content) == 1
        assert "Real content" in result.content[0]

    def it_handles_string_content_directly(api: DigestAPI, raw_dir, processed_dir):
        """User messages can have string content directly."""
        msg = {"type": "user", "message": {"content": "Direct string content"}}
        path = raw_dir / "string.jsonl"
        with open(path, "w") as f:
            f.write(json.dumps(msg) + "\n")

        result = api.extract("string")

        assert "Direct string content" in result.content[0]


def describe_full_workflow():
    """End-to-end workflow tests."""

    def it_processes_transcript_completely(api: DigestAPI, raw_dir, processed_dir):
        """Complete workflow: list -> extract -> mark -> list."""
        messages = [
            make_user_message("Hello"),
            make_assistant_message("Hi there!"),
            make_tool_use("Read", {"file": "/x"}),
            make_tool_result("file contents"),
            make_assistant_message("Found it."),
        ]
        write_transcript(raw_dir / "workflow.jsonl", messages)

        # 1. List shows new transcript
        transcripts = api.list_transcripts()
        assert len(transcripts) == 1
        assert transcripts[0].session_id == "workflow"

        # 2. Extract all content
        result = api.extract("workflow")
        assert len(result.content) == 5
        assert result.next_cursor is None

        # 3. Mark as processed
        mark_result = api.mark_processed("workflow")
        assert mark_result.lines_marked == 5

        # 4. List shows nothing new
        transcripts = api.list_transcripts()
        assert transcripts == []

    def it_handles_incremental_workflow(api: DigestAPI, raw_dir, processed_dir):
        """Incremental processing workflow."""
        path = raw_dir / "incremental.jsonl"

        # Initial content
        write_transcript(path, [make_user_message("Day 1")])

        # Process day 1
        api.extract("incremental")
        api.mark_processed("incremental")

        # Add day 2
        append_to_transcript(path, [make_user_message("Day 2")])

        # List shows new content
        transcripts = api.list_transcripts()
        assert len(transcripts) == 1
        assert transcripts[0].new_lines == 1

        # Extract only new
        result = api.extract("incremental")
        assert result.start_line == 2
        assert "Day 2" in result.content[0]

        # Mark again
        api.mark_processed("incremental")

        # Nothing new
        transcripts = api.list_transcripts()
        assert transcripts == []


def describe_fixture_files():
    """Tests using pre-made fixture files."""

    def it_extracts_from_malformed_fixture(api: DigestAPI, fixture_malformed):
        """Handles malformed JSON lines from fixture."""
        result = api.extract("malformed_lines")

        content = "\n".join(result.content)
        assert "Good line 1" in content
        assert "Good line 2" in content
        assert "Good response" in content
        assert "Good line 3" in content

    def it_extracts_unicode_fixture(api: DigestAPI, fixture_unicode):
        """Handles unicode content from fixture."""
        result = api.extract("unicode_content")

        # Check various unicode characters made it through
        assert len(result.content) == 4
        # Verify content is not empty
        assert all(len(c) > 0 for c in result.content)

    def it_extracts_mixed_content_fixture(api: DigestAPI, fixture_mixed):
        """Handles mixed content types from fixture."""
        result = api.extract("mixed_content_types")

        content = "\n".join(result.content)
        assert "Start task" in content
        assert "[TOOL USE: Read]" in content
        assert "[TOOL RESULT]:" in content

    def it_extracts_real_format_fixture(api: DigestAPI, fixture_real_format):
        """Handles real Claude format from fixture."""
        result = api.extract("real_claude_format")

        content = "\n".join(result.content)
        assert "config file" in content
        assert "[TOOL USE: Read]" in content
        assert "theme" in content.lower() or "settings" in content.lower()

    def it_handles_empty_contents_fixture(api: DigestAPI, fixture_empty_contents):
        """Handles empty content messages from fixture."""
        result = api.extract("empty_contents")

        # Only messages with actual content should be extracted
        assert len(result.content) == 2
        assert "Actually has content" in result.content[0]
        assert "Real response here" in result.content[1]

    def it_extracts_thinking_blocks_fixture(api: DigestAPI, fixture_thinking):
        """Handles thinking blocks from fixture."""
        result = api.extract("thinking_blocks")

        content = "\n".join(result.content)
        assert "[THINKING]:" in content
        assert "factorial" in content.lower()
        assert "[TOOL USE: Write]" in content

    def it_distinguishes_error_and_success_results(api: DigestAPI, fixture_errors):
        """Error tool results get [TOOL ERROR], successes get [TOOL RESULT]."""
        result = api.extract("error_results")

        content = "\n".join(result.content)
        # Should have both error and success markers
        assert "[TOOL ERROR]:" in content
        assert "[TOOL RESULT]:" in content
        # Error content
        assert "File not found" in content
        assert "command not found" in content
        # Success content
        assert "myhost" in content
