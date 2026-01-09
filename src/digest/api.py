"""
Core Python API for digest transcript processing.

This module provides the programmatic API. The CLI wraps these functions.
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


# Configuration
DEFAULT_CHAR_BUDGET = 50_000  # ~50KB per extraction
LINE_OVERLAP = 10  # Lines of overlap between extractions


@dataclass
class TranscriptStatus:
    """Status of a transcript file."""

    session_id: str
    processed_lines: int
    total_lines: int

    @property
    def new_lines(self) -> int:
        return max(0, self.total_lines - self.processed_lines)

    @property
    def has_new_content(self) -> bool:
        return self.new_lines > 0


@dataclass
class ExtractResult:
    """Result of extracting content from a transcript."""

    session_id: str
    start_line: int
    end_line: int
    total_lines: int
    content: list[str]  # List of formatted messages
    total_chars: int
    next_cursor: int | None  # None if at end of transcript


@dataclass
class MarkResult:
    """Result of marking a transcript as processed."""

    session_id: str
    lines_marked: int


@dataclass
class NoteResult:
    """Result of adding a note to a digest file."""

    file_path: Path
    timestamp: str
    lines_added: int


class DigestAPI:
    """API for transcript processing operations."""

    def __init__(self, base_dir: Path | str | None = None):
        """
        Initialize the API.

        Args:
            base_dir: Base directory containing notes/logs/. Defaults to cwd.
        """
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        self.raw_dir = self.base_dir / "notes" / "logs" / "raw"
        self.processed_dir = self.base_dir / "notes" / "logs" / "processed"

    def _ensure_processed_dir(self) -> None:
        """Ensure processed directory exists."""
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def _get_processed_lines(self, session_id: str) -> int:
        """Get number of lines already processed for a session."""
        processed_file = self.processed_dir / f"{session_id}.json"
        if processed_file.exists():
            data = json.loads(processed_file.read_text())
            return data.get("lineNumber", 0)
        return 0

    def _get_total_lines(self, file_path: Path) -> int:
        """Count total lines in a file."""
        if not file_path.exists():
            return 0
        with open(file_path) as f:
            return sum(1 for _ in f)

    def _extract_message_content(self, message: dict) -> str | None:
        """Extract text content from a message, including tool use/results."""
        content = message.get("message", {}).get("content")

        if content is None:
            return None

        if isinstance(content, str):
            return content if content else None

        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    item_type = item.get("type")
                    if item_type == "text":
                        text = item.get("text", "")
                        if text:
                            parts.append(text)
                    elif item_type == "tool_use":
                        name = item.get("name", "unknown")
                        inp = json.dumps(item.get("input", {}))
                        parts.append(f"[TOOL USE: {name}]: {inp}")
                    elif item_type == "tool_result":
                        tool_content = item.get("content", "")
                        is_error = item.get("is_error", False)
                        prefix = "[TOOL ERROR]" if is_error else "[TOOL RESULT]"
                        if isinstance(tool_content, str):
                            parts.append(f"{prefix}: {tool_content}")
                        elif isinstance(tool_content, list):
                            texts = [
                                c.get("text", "")
                                for c in tool_content
                                if isinstance(c, dict)
                            ]
                            parts.append(f"{prefix}: {' '.join(texts)}")
                        else:
                            parts.append(prefix)
                    elif item_type == "thinking":
                        thinking_text = item.get("thinking", "")
                        if thinking_text:
                            parts.append(f"[THINKING]: {thinking_text}")

            result = "\n".join(p for p in parts if p)
            return result if result else None

        return None

    def list_transcripts(self) -> list[TranscriptStatus]:
        """
        List all transcripts with their processing status.

        Returns:
            List of TranscriptStatus objects for transcripts with new content.
        """
        self._ensure_processed_dir()

        if not self.raw_dir.exists():
            return []

        results = []
        for f in sorted(self.raw_dir.glob("*.jsonl")):
            session_id = f.stem
            processed = self._get_processed_lines(session_id)
            total = self._get_total_lines(f)
            status = TranscriptStatus(
                session_id=session_id,
                processed_lines=processed,
                total_lines=total,
            )
            if status.has_new_content:
                results.append(status)

        return results

    def extract(
        self,
        session_id: str,
        cursor: int | None = None,
        char_budget: int = DEFAULT_CHAR_BUDGET,
    ) -> ExtractResult:
        """
        Extract content from a transcript starting at cursor line.

        Args:
            session_id: The session ID (filename without .jsonl)
            cursor: Line number to start from (1-indexed). Defaults to line after
                    last processed, or 1 if no processed state.
            char_budget: Maximum characters to extract. A single line exceeding
                         this will still be returned in full.

        Returns:
            ExtractResult with content and pagination info.

        Raises:
            FileNotFoundError: If transcript doesn't exist.
        """
        self._ensure_processed_dir()
        file_path = self.raw_dir / f"{session_id}.jsonl"

        if not file_path.exists():
            raise FileNotFoundError(f"Transcript not found: {file_path}")

        total_lines = self._get_total_lines(file_path)

        # Default cursor: start after last processed line, or line 1
        if cursor is None:
            processed = self._get_processed_lines(session_id)
            cursor = processed + 1 if processed > 0 else 1

        # Handle cursor beyond file
        if cursor > total_lines:
            return ExtractResult(
                session_id=session_id,
                start_line=cursor,
                end_line=cursor - 1,
                total_lines=total_lines,
                content=[],
                total_chars=0,
                next_cursor=None,
            )

        # Extract content with character budget
        extracted_lines: list[str] = []
        total_chars = 0
        last_line_read = cursor - 1

        with open(file_path) as f:
            for i, line in enumerate(f, 1):
                if i < cursor:
                    continue

                last_line_read = i

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if not isinstance(data, dict):
                    continue

                msg_type = data.get("type")
                if msg_type not in ("user", "assistant"):
                    continue

                content = self._extract_message_content(data)
                if not content:
                    continue

                formatted = f"[{msg_type.upper()}]: {content}"
                line_chars = len(formatted)

                # If we'd exceed budget and already have content, stop before this line
                if total_chars + line_chars > char_budget and extracted_lines:
                    last_line_read = i - 1
                    break

                # Add the line (even if it alone exceeds budget)
                extracted_lines.append(formatted)
                total_chars += line_chars

        # Calculate next cursor (with overlap)
        end_line = last_line_read
        if end_line < total_lines:
            next_cursor = max(cursor, end_line - LINE_OVERLAP + 1)
        else:
            next_cursor = None

        return ExtractResult(
            session_id=session_id,
            start_line=cursor,
            end_line=end_line,
            total_lines=total_lines,
            content=extracted_lines,
            total_chars=total_chars,
            next_cursor=next_cursor,
        )

    def mark_processed(self, session_id: str) -> MarkResult:
        """
        Mark a transcript as fully processed.

        Args:
            session_id: The session ID (filename without .jsonl)

        Returns:
            MarkResult with the number of lines marked.

        Raises:
            FileNotFoundError: If transcript doesn't exist.
        """
        self._ensure_processed_dir()
        file_path = self.raw_dir / f"{session_id}.jsonl"

        if not file_path.exists():
            raise FileNotFoundError(f"Transcript not found: {file_path}")

        total = self._get_total_lines(file_path)
        processed_file = self.processed_dir / f"{session_id}.json"
        processed_file.write_text(json.dumps({"lineNumber": total}))

        return MarkResult(session_id=session_id, lines_marked=total)

    def add_note(
        self,
        file_path: str | Path,
        text: str,
        project: str | None = None,
    ) -> NoteResult:
        """
        Prepend timestamped note entry to a digest file.

        Args:
            file_path: Target file path (relative to base_dir or absolute)
            text: Text to add (should include inline source refs like [session:line])
            project: Optional project name for ## header

        Returns:
            NoteResult with file path, timestamp, and lines added.
        """
        # Resolve file path
        path = Path(file_path)
        if not path.is_absolute():
            path = self.base_dir / path

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Get timestamp from system
        result = subprocess.run(
            ["date", "+%Y-%m-%d %H:%M"],
            capture_output=True,
            text=True,
            check=True,
        )
        timestamp = result.stdout.strip()

        # Build entry block
        lines = text.strip().split("\n")
        entry_parts = ["---", f"### {timestamp}"]

        if project:
            entry_parts.append("")
            entry_parts.append(f"## {project}")

        entry_parts.append("")
        entry_parts.extend(lines)
        entry_parts.append("")

        entry = "\n".join(entry_parts)

        # Read existing content if file exists
        existing = ""
        if path.exists():
            existing = path.read_text()

        # Prepend entry to file
        path.write_text(entry + existing)

        return NoteResult(
            file_path=path,
            timestamp=timestamp,
            lines_added=len(lines),
        )


# Module-level convenience functions using default API instance
_default_api: DigestAPI | None = None


def _get_api() -> DigestAPI:
    """Get or create default API instance."""
    global _default_api
    if _default_api is None:
        _default_api = DigestAPI()
    return _default_api


def list_transcripts() -> list[TranscriptStatus]:
    """List transcripts with new content. See DigestAPI.list_transcripts."""
    return _get_api().list_transcripts()


def extract(
    session_id: str,
    cursor: int | None = None,
    char_budget: int = DEFAULT_CHAR_BUDGET,
) -> ExtractResult:
    """Extract content from transcript. See DigestAPI.extract."""
    return _get_api().extract(session_id, cursor, char_budget)


def mark_processed(session_id: str) -> MarkResult:
    """Mark transcript as processed. See DigestAPI.mark_processed."""
    return _get_api().mark_processed(session_id)
