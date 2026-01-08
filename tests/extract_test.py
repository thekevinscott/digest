"""Tests for the extract API function."""

import pytest

from digest import DigestAPI
from conftest import (
    make_user_message,
    make_assistant_message,
    make_tool_use,
    make_tool_result,
    make_mixed_assistant,
    make_thinking_message,
    write_transcript,
    mark_processed,
)


def describe_extract():
    """Tests for extracting transcript content."""

    def describe_message_formatting():
        """Tests for how different message types are formatted."""

        def it_extracts_user_messages_with_prefix(api: DigestAPI, raw_dir, processed_dir):
            """User messages get [USER] prefix."""
            write_transcript(
                raw_dir / "test.jsonl",
                [make_user_message("Hello world")],
            )

            result = api.extract("test")

            assert len(result.content) == 1
            assert "[USER]: Hello world" in result.content[0]

        def it_extracts_assistant_text_with_prefix(api: DigestAPI, raw_dir, processed_dir):
            """Assistant text messages get [ASSISTANT] prefix."""
            write_transcript(
                raw_dir / "test.jsonl",
                [make_assistant_message("I can help with that")],
            )

            result = api.extract("test")

            assert len(result.content) == 1
            assert "[ASSISTANT]: I can help with that" in result.content[0]

        def it_extracts_tool_use_with_name_and_input(api: DigestAPI, raw_dir, processed_dir):
            """Tool use messages include tool name and input JSON."""
            write_transcript(
                raw_dir / "test.jsonl",
                [make_tool_use("Read", {"file_path": "/tmp/foo.txt"})],
            )

            result = api.extract("test")

            assert len(result.content) == 1
            content = result.content[0]
            assert "[ASSISTANT]:" in content
            assert "[TOOL USE: Read]" in content
            assert "file_path" in content
            assert "/tmp/foo.txt" in content

        def it_extracts_tool_result_content(api: DigestAPI, raw_dir, processed_dir):
            """Tool result messages include their content."""
            write_transcript(
                raw_dir / "test.jsonl",
                [make_tool_result("File contents here")],
            )

            result = api.extract("test")

            assert len(result.content) == 1
            assert "[USER]:" in result.content[0]
            assert "[TOOL RESULT]: File contents here" in result.content[0]

        def it_extracts_tool_result_with_array_content(api: DigestAPI, raw_dir, processed_dir):
            """Tool results with array content are joined."""
            write_transcript(
                raw_dir / "test.jsonl",
                [make_tool_result(["Line 1", "Line 2", "Line 3"])],
            )

            result = api.extract("test")

            content = result.content[0]
            assert "[TOOL RESULT]:" in content
            assert "Line 1" in content
            assert "Line 2" in content

        def it_extracts_error_tool_results(api: DigestAPI, raw_dir, processed_dir):
            """Error tool results are extracted with [TOOL ERROR] marker."""
            import json
            msg = {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "content": "File not found: /nonexistent.txt",
                            "is_error": True,
                            "tool_use_id": "toolu_123",
                        }
                    ]
                },
            }
            path = raw_dir / "test.jsonl"
            with open(path, "w") as f:
                f.write(json.dumps(msg) + "\n")

            result = api.extract("test")

            content = result.content[0]
            assert "[TOOL ERROR]:" in content
            assert "File not found" in content

        def it_extracts_success_tool_results_without_error_marker(
            api: DigestAPI, raw_dir, processed_dir
        ):
            """Successful tool results use [TOOL RESULT], not [TOOL ERROR]."""
            write_transcript(
                raw_dir / "test.jsonl",
                [make_tool_result("Success!")],
            )

            result = api.extract("test")

            content = result.content[0]
            assert "[TOOL RESULT]:" in content
            assert "[TOOL ERROR]" not in content

        def it_extracts_mixed_text_and_tool_use(api: DigestAPI, raw_dir, processed_dir):
            """Messages with both text and tool use show both."""
            write_transcript(
                raw_dir / "test.jsonl",
                [make_mixed_assistant("Let me check", "Read", {"path": "/x"})],
            )

            result = api.extract("test")

            content = result.content[0]
            assert "Let me check" in content
            assert "[TOOL USE: Read]" in content

        def it_extracts_thinking_blocks(api: DigestAPI, raw_dir, processed_dir):
            """Thinking blocks are extracted with [THINKING] prefix."""
            write_transcript(
                raw_dir / "test.jsonl",
                [make_thinking_message("Let me analyze this problem", "Here's my answer")],
            )

            result = api.extract("test")

            content = result.content[0]
            assert "[THINKING]: Let me analyze this problem" in content
            assert "Here's my answer" in content

        def it_extracts_thinking_with_tool_use(api: DigestAPI, raw_dir, processed_dir):
            """Messages with thinking, text, and tool use show all."""
            msg = {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "thinking", "thinking": "I need to read the file first"},
                        {"type": "text", "text": "Let me check that file."},
                        {"type": "tool_use", "name": "Read", "input": {"path": "/x"}},
                    ]
                },
            }
            path = raw_dir / "test.jsonl"
            import json
            with open(path, "w") as f:
                f.write(json.dumps(msg) + "\n")

            result = api.extract("test")

            content = result.content[0]
            assert "[THINKING]: I need to read the file first" in content
            assert "Let me check that file" in content
            assert "[TOOL USE: Read]" in content

    def describe_cursor_behavior():
        """Tests for cursor-based pagination."""

        def it_starts_from_line_1_by_default(api: DigestAPI, raw_dir, processed_dir):
            """Without cursor, extraction starts from line 1."""
            write_transcript(
                raw_dir / "test.jsonl",
                [
                    make_user_message("First"),
                    make_user_message("Second"),
                    make_user_message("Third"),
                ],
            )

            result = api.extract("test")

            assert result.start_line == 1
            assert result.end_line == 3
            assert "First" in result.content[0]

        def it_starts_from_cursor_line(api: DigestAPI, raw_dir, processed_dir):
            """With cursor, extraction starts from that line."""
            write_transcript(
                raw_dir / "test.jsonl",
                [
                    make_user_message("First"),
                    make_user_message("Second"),
                    make_user_message("Third"),
                ],
            )

            result = api.extract("test", cursor=2)

            assert result.start_line == 2
            assert result.end_line == 3
            assert all("First" not in c for c in result.content)
            assert any("Second" in c for c in result.content)

        def it_defaults_to_after_processed_line(api: DigestAPI, raw_dir, processed_dir):
            """Without cursor, starts after last processed line."""
            write_transcript(
                raw_dir / "test.jsonl",
                [
                    make_user_message("Old"),
                    make_user_message("New"),
                ],
            )
            mark_processed(processed_dir, "test", 1)

            result = api.extract("test")

            assert result.start_line == 2
            assert result.end_line == 2
            assert all("Old" not in c for c in result.content)
            assert any("New" in c for c in result.content)

        def it_returns_none_cursor_when_done(api: DigestAPI, raw_dir, processed_dir):
            """When reaching end of file, next_cursor is None."""
            write_transcript(
                raw_dir / "test.jsonl",
                [make_user_message("Only line")],
            )

            result = api.extract("test")

            assert result.next_cursor is None

        def it_returns_cursor_for_more_content(api: DigestAPI, raw_dir, processed_dir):
            """When more content remains, returns next cursor."""
            messages = [make_user_message("x" * 1000) for _ in range(100)]
            write_transcript(raw_dir / "test.jsonl", messages)

            result = api.extract("test", char_budget=5000)

            assert result.next_cursor is not None
            assert result.next_cursor < 100

        def it_handles_cursor_beyond_file(api: DigestAPI, raw_dir, processed_dir):
            """Cursor beyond file length returns empty result."""
            write_transcript(
                raw_dir / "test.jsonl",
                [make_user_message("Only")],
            )

            result = api.extract("test", cursor=100)

            assert result.content == []
            assert result.start_line == 100
            assert result.end_line == 99  # Before start
            assert result.next_cursor is None

    def describe_character_budget():
        """Tests for character budget limiting."""

        def it_respects_character_budget(api: DigestAPI, raw_dir, processed_dir):
            """Stops when character budget is reached."""
            messages = [make_user_message("x" * 990) for _ in range(20)]
            write_transcript(raw_dir / "test.jsonl", messages)

            result = api.extract("test", char_budget=5000)

            assert result.end_line < 20
            assert result.total_chars <= 6000  # Some slack for formatting
            assert result.next_cursor is not None

        def it_returns_huge_line_even_if_over_budget(api: DigestAPI, raw_dir, processed_dir):
            """A single line exceeding budget is still returned."""
            huge_content = "x" * 100_000  # 100KB
            write_transcript(
                raw_dir / "test.jsonl",
                [make_user_message(huge_content)],
            )

            result = api.extract("test", char_budget=50_000)

            assert len(result.content) == 1
            assert huge_content in result.content[0]
            assert result.total_chars > 100_000

        def it_stops_before_line_that_would_exceed(api: DigestAPI, raw_dir, processed_dir):
            """Stops before adding a line that would exceed budget."""
            messages = [
                make_user_message("Small"),
                make_user_message("x" * 10_000),
            ]
            write_transcript(raw_dir / "test.jsonl", messages)

            result = api.extract("test", char_budget=100)

            assert len(result.content) == 1
            assert "Small" in result.content[0]
            assert result.end_line == 1
            assert result.next_cursor is not None

    def describe_error_handling():
        """Tests for error conditions."""

        def it_raises_on_missing_transcript(api: DigestAPI, raw_dir, processed_dir):
            """Missing transcript file raises FileNotFoundError."""
            with pytest.raises(FileNotFoundError):
                api.extract("nonexistent")

        def it_skips_malformed_json_lines(api: DigestAPI, raw_dir, processed_dir):
            """Malformed JSON lines are skipped gracefully."""
            path = raw_dir / "test.jsonl"
            with open(path, "w") as f:
                f.write('{"type": "user", "message": {"content": "Good"}}\n')
                f.write("not valid json\n")
                f.write('{"type": "user", "message": {"content": "Also good"}}\n')

            result = api.extract("test")

            content = "\n".join(result.content)
            assert "Good" in content
            assert "Also good" in content

        def it_skips_non_user_assistant_types(api: DigestAPI, raw_dir, processed_dir):
            """Only user and assistant message types are extracted."""
            path = raw_dir / "test.jsonl"
            with open(path, "w") as f:
                f.write('{"type": "user", "message": {"content": "User msg"}}\n')
                f.write('{"type": "system", "message": {"content": "System"}}\n')
                f.write('{"type": "metadata", "data": {}}\n')
                f.write('{"type": "assistant", "message": {"content": [{"type": "text", "text": "Asst"}]}}\n')

            result = api.extract("test")

            content = "\n".join(result.content)
            assert "User msg" in content
            assert "Asst" in content
            assert "System" not in content

    def describe_large_files():
        """Tests for handling large transcript files."""

        def it_handles_file_with_thousands_of_lines(api: DigestAPI, raw_dir, processed_dir):
            """Can process files with many lines."""
            messages = [make_user_message(f"Message {i}") for i in range(1000)]
            write_transcript(raw_dir / "large.jsonl", messages)

            result = api.extract("large", char_budget=10_000)

            assert result.total_lines == 1000
            assert result.next_cursor is not None

        def it_paginates_through_large_file(api: DigestAPI, raw_dir, processed_dir):
            """Multiple extract calls can page through large file."""
            messages = [make_user_message(f"Line {i:04d}") for i in range(500)]
            write_transcript(raw_dir / "paginate.jsonl", messages)

            # First extraction
            result1 = api.extract("paginate", cursor=1, char_budget=5000)
            assert result1.next_cursor is not None
            assert result1.next_cursor > 1
            assert result1.next_cursor < 500

            # Second extraction from cursor
            result2 = api.extract("paginate", cursor=result1.next_cursor, char_budget=5000)
            assert result2.start_line == result1.next_cursor

        def it_eventually_reaches_end_of_large_file(api: DigestAPI, raw_dir, processed_dir):
            """Pagination eventually reaches end of file."""
            messages = [make_user_message(f"Msg {i}") for i in range(100)]
            write_transcript(raw_dir / "finite.jsonl", messages)

            cursor = 1
            iterations = 0

            while iterations < 50:
                result = api.extract("finite", cursor=cursor, char_budget=2000)
                if result.next_cursor is None:
                    break
                cursor = result.next_cursor
                iterations += 1

            assert result.next_cursor is None
            assert iterations < 50

    def describe_oversized_lines():
        """Tests for lines that exceed the character budget."""

        def it_returns_single_huge_line_on_first_call(api: DigestAPI, raw_dir, processed_dir):
            """A single huge line is returned even if it exceeds budget."""
            huge_content = "A" * 200_000  # 200KB
            write_transcript(
                raw_dir / "huge.jsonl",
                [make_user_message(huge_content)],
            )

            result = api.extract("huge", char_budget=50_000)

            assert len(result.content) == 1
            assert huge_content in result.content[0]
            assert result.total_chars > 200_000
            assert result.next_cursor is None

        def it_returns_huge_line_after_small_ones(api: DigestAPI, raw_dir, processed_dir):
            """Stops before huge line if small content already extracted."""
            messages = [
                make_user_message("Small message 1"),
                make_user_message("Small message 2"),
                make_user_message("B" * 100_000),
            ]
            write_transcript(raw_dir / "mixed.jsonl", messages)

            result = api.extract("mixed", char_budget=1000)

            assert any("Small message 1" in c for c in result.content)
            assert any("Small message 2" in c for c in result.content)
            assert all("B" * 100 not in c for c in result.content)
            assert result.end_line == 2
            assert result.next_cursor is not None

        def it_returns_huge_line_on_subsequent_call(api: DigestAPI, raw_dir, processed_dir):
            """Huge line is returned when it's the first line of extraction."""
            messages = [
                make_user_message("Small"),
                make_user_message("C" * 150_000),
                make_user_message("After"),
            ]
            write_transcript(raw_dir / "sequence.jsonl", messages)

            result = api.extract("sequence", cursor=2, char_budget=50_000)

            assert len(result.content) == 1
            assert "C" * 1000 in result.content[0]
            assert result.total_chars > 150_000
            assert result.next_cursor is not None  # Line 3 remains

        def it_handles_multiple_huge_lines(api: DigestAPI, raw_dir, processed_dir):
            """Each huge line requires its own extraction call."""
            messages = [
                make_user_message("D" * 100_000),
                make_user_message("E" * 100_000),
            ]
            write_transcript(raw_dir / "two-huge.jsonl", messages)

            result1 = api.extract("two-huge", cursor=1, char_budget=50_000)
            assert "D" * 1000 in result1.content[0]
            assert result1.end_line == 1

            result2 = api.extract("two-huge", cursor=2, char_budget=50_000)
            assert "E" * 1000 in result2.content[0]
            assert result2.end_line == 2

        def it_handles_huge_tool_result(api: DigestAPI, raw_dir, processed_dir):
            """Huge tool results are also returned without truncation."""
            huge_result = "F" * 200_000
            write_transcript(
                raw_dir / "huge-tool.jsonl",
                [make_tool_result(huge_result)],
            )

            result = api.extract("huge-tool", char_budget=50_000)

            assert "[TOOL RESULT]:" in result.content[0]
            assert huge_result in result.content[0]

    def describe_result_metadata():
        """Tests for ExtractResult metadata."""

        def it_includes_session_id(api: DigestAPI, raw_dir, processed_dir):
            """Result includes session ID."""
            write_transcript(
                raw_dir / "my-session.jsonl",
                [make_user_message("Test")],
            )

            result = api.extract("my-session")

            assert result.session_id == "my-session"

        def it_includes_line_range(api: DigestAPI, raw_dir, processed_dir):
            """Result includes start and end line numbers."""
            write_transcript(
                raw_dir / "test.jsonl",
                [make_user_message(f"Line {i}") for i in range(10)],
            )

            result = api.extract("test", cursor=3)

            assert result.start_line == 3
            assert result.end_line == 10
            assert result.total_lines == 10

        def it_includes_total_chars(api: DigestAPI, raw_dir, processed_dir):
            """Result includes character count."""
            write_transcript(
                raw_dir / "test.jsonl",
                [make_user_message("x" * 1000)],
            )

            result = api.extract("test")

            assert result.total_chars > 1000  # Content + formatting
