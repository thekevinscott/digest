"""
CLI wrapper for digest transcript processing.

This module provides the command-line interface. It wraps the API module.
"""

import argparse
import sys

from .api import DigestAPI


def cmd_list(api: DigestAPI) -> None:
    """Handle list command."""
    transcripts = api.list_transcripts()

    if not transcripts:
        print("Nothing new to process")
        return

    for t in transcripts:
        print(f"{t.session_id}: {t.processed_lines}/{t.total_lines} ({t.new_lines} new)")


def cmd_extract(api: DigestAPI, session_id: str, cursor: int | None) -> None:
    """Handle extract command."""
    try:
        result = api.extract(session_id, cursor)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Handle cursor beyond file
    if result.start_line > result.total_lines:
        print(f"--- Session: {result.session_id} ---")
        print(
            f"--- No content (cursor {result.start_line} beyond end of file {result.total_lines}) ---"
        )
        return

    # Output header
    kb = result.total_chars // 1000
    print(
        f"--- Session: {result.session_id}, lines {result.start_line}-{result.end_line} "
        f"of {result.total_lines} (~{kb}KB) ---"
    )
    print()

    # Output content
    for line in result.content:
        print(line)

    # Output cursor or end marker
    print()
    if result.next_cursor is not None:
        print(f"--- cursor: {result.next_cursor} ---")
    else:
        print("--- end of transcript ---")


def cmd_mark(api: DigestAPI, session_id: str) -> None:
    """Handle mark command."""
    try:
        result = api.mark_processed(session_id)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Marked {result.session_id} as processed ({result.lines_marked} lines)")


def cmd_note(api: DigestAPI, file_path: str, text: str | None, project: str | None) -> None:
    """Handle note command."""
    # Read from stdin if no text argument
    if text is None:
        if sys.stdin.isatty():
            print("Error: No text provided (use argument or pipe via stdin)", file=sys.stderr)
            sys.exit(1)
        text = sys.stdin.read()

    if not text.strip():
        print("Error: Empty text provided", file=sys.stderr)
        sys.exit(1)

    try:
        result = api.add_note(file_path, text, project)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Added {result.lines_added} lines to {result.file_path}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract insights from Claude Code transcripts"
    )
    parser.add_argument(
        "--path",
        metavar="DIR",
        help="Base directory containing notes/logs/ (default: cwd)",
    )

    subparsers = parser.add_subparsers(dest="command")

    # list
    subparsers.add_parser("list", help="Show transcripts with unprocessed lines")

    # extract
    extract_parser = subparsers.add_parser("extract", help="Extract content from transcript")
    extract_parser.add_argument("session_id", help="Session ID")
    extract_parser.add_argument("cursor", nargs="?", type=int, help="Start line number")

    # mark
    mark_parser = subparsers.add_parser("mark", help="Mark transcript as fully processed")
    mark_parser.add_argument("session_id", help="Session ID")

    # note
    note_parser = subparsers.add_parser("note", help="Add timestamped note to digest file")
    note_parser.add_argument("file", help="Target file path")
    note_parser.add_argument("text", nargs="?", help="Text to add (or use stdin)")
    note_parser.add_argument("--project", metavar="NAME", help="Project name for header")

    args = parser.parse_args()
    api = DigestAPI(base_dir=args.path)

    match args.command:
        case "list" | None:
            cmd_list(api)
        case "extract":
            cmd_extract(api, args.session_id, args.cursor)
        case "mark":
            cmd_mark(api, args.session_id)
        case "note":
            cmd_note(api, args.file, args.text, args.project)


if __name__ == "__main__":
    main()
