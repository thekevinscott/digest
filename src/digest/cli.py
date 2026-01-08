"""
CLI wrapper for digest transcript processing.

This module provides the command-line interface. It wraps the API module.
"""

import argparse
import sys

from .api import DigestAPI


def cmd_list(api: DigestAPI) -> None:
    """Handle --list command."""
    transcripts = api.list_transcripts()

    if not transcripts:
        print("Nothing new to process")
        return

    for t in transcripts:
        print(f"{t.session_id}: {t.processed_lines}/{t.total_lines} ({t.new_lines} new)")


def cmd_extract(api: DigestAPI, session_id: str, cursor: int | None) -> None:
    """Handle --extract command."""
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
    """Handle --mark command."""
    try:
        result = api.mark_processed(session_id)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Marked {result.session_id} as processed ({result.lines_marked} lines)")


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
    parser.add_argument(
        "--list", action="store_true", help="Show transcripts with unprocessed lines"
    )
    parser.add_argument("--extract", metavar="ID", help="Extract content from transcript")
    parser.add_argument("--mark", metavar="ID", help="Mark transcript as fully processed")
    parser.add_argument(
        "cursor",
        nargs="?",
        type=int,
        default=None,
        help="Line number to start extraction from",
    )

    args = parser.parse_args()
    api = DigestAPI(base_dir=args.path)

    if args.list or (not args.extract and not args.mark):
        cmd_list(api)
    elif args.extract:
        cmd_extract(api, args.extract, args.cursor)
    elif args.mark:
        cmd_mark(api, args.mark)


if __name__ == "__main__":
    main()
