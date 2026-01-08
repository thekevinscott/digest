"""
digest - Extract insights from Claude Code transcripts into artifact files.

Usage:
    digest --list                    Show transcripts with unprocessed lines
    digest --extract <id> [cursor]   Extract content starting from cursor line
    digest --mark <id>               Mark transcript as fully processed
"""

# Re-export API
from .api import (
    DEFAULT_CHAR_BUDGET,
    LINE_OVERLAP,
    DigestAPI,
    ExtractResult,
    MarkResult,
    TranscriptStatus,
    extract,
    list_transcripts,
    mark_processed,
)

# CLI entry point
from .cli import main

__all__ = [
    # Constants
    "DEFAULT_CHAR_BUDGET",
    "LINE_OVERLAP",
    # Classes
    "DigestAPI",
    "ExtractResult",
    "MarkResult",
    "TranscriptStatus",
    # Functions
    "extract",
    "list_transcripts",
    "mark_processed",
    "main",
]
