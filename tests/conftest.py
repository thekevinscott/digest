"""Shared fixtures for digest tests."""

import json
import shutil
import sys
from pathlib import Path

import pytest

# Add tests dir to path so test files can import from conftest
sys.path.insert(0, str(Path(__file__).parent))

from digest import DigestAPI


FIXTURES_DIR = Path(__file__).parent / "__fixtures__"


@pytest.fixture
def temp_cwd(tmp_path, monkeypatch):
    """Change to a temporary directory for tests."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def api(temp_cwd) -> DigestAPI:
    """Create a DigestAPI instance pointing to temp directory."""
    return DigestAPI(base_dir=temp_cwd)


@pytest.fixture
def raw_dir(temp_cwd):
    """Create and return the raw logs directory."""
    d = temp_cwd / "notes" / "logs" / "raw"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def processed_dir(temp_cwd):
    """Create and return the processed logs directory."""
    d = temp_cwd / "notes" / "logs" / "processed"
    d.mkdir(parents=True)
    return d


# --- Message builders ---


def make_message(msg_type: str, content: str | list) -> dict:
    """Create a transcript message in Claude Code format."""
    return {
        "type": msg_type,
        "message": {"content": content},
    }


def make_user_message(text: str) -> dict:
    """Create a user message."""
    return make_message("user", text)


def make_assistant_message(text: str) -> dict:
    """Create an assistant text message."""
    return make_message("assistant", [{"type": "text", "text": text}])


def make_tool_use(name: str, input_data: dict) -> dict:
    """Create an assistant message with tool use."""
    return make_message(
        "assistant",
        [{"type": "tool_use", "name": name, "input": input_data}],
    )


def make_tool_result(content: str | list) -> dict:
    """Create a user message with tool result."""
    if isinstance(content, str):
        tool_content = content
    else:
        tool_content = [{"type": "text", "text": t} for t in content]
    return make_message(
        "user",
        [{"type": "tool_result", "content": tool_content}],
    )


def make_mixed_assistant(text: str, tool_name: str, tool_input: dict) -> dict:
    """Create an assistant message with both text and tool use."""
    return make_message(
        "assistant",
        [
            {"type": "text", "text": text},
            {"type": "tool_use", "name": tool_name, "input": tool_input},
        ],
    )


# --- File helpers ---


def write_transcript(path: Path, messages: list[dict]) -> None:
    """Write a list of messages to a JSONL transcript file."""
    with open(path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")


def append_to_transcript(path: Path, messages: list[dict]) -> None:
    """Append messages to an existing transcript file."""
    with open(path, "a") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")


def mark_processed(processed_dir: Path, session_id: str, line_number: int) -> None:
    """Create a processed state file."""
    processed_file = processed_dir / f"{session_id}.json"
    processed_file.write_text(json.dumps({"lineNumber": line_number}))


# --- Fixture file loading ---


def load_fixture(name: str, raw_dir: Path) -> Path:
    """Copy a fixture file to the raw directory and return its path."""
    src = FIXTURES_DIR / name
    dst = raw_dir / name
    shutil.copy(src, dst)
    return dst


@pytest.fixture
def fixture_malformed(raw_dir) -> Path:
    """Load the malformed_lines fixture."""
    return load_fixture("malformed_lines.jsonl", raw_dir)


@pytest.fixture
def fixture_unicode(raw_dir) -> Path:
    """Load the unicode_content fixture."""
    return load_fixture("unicode_content.jsonl", raw_dir)


@pytest.fixture
def fixture_mixed(raw_dir) -> Path:
    """Load the mixed_content_types fixture."""
    return load_fixture("mixed_content_types.jsonl", raw_dir)


@pytest.fixture
def fixture_real_format(raw_dir) -> Path:
    """Load the real_claude_format fixture."""
    return load_fixture("real_claude_format.jsonl", raw_dir)


@pytest.fixture
def fixture_empty_contents(raw_dir) -> Path:
    """Load the empty_contents fixture."""
    return load_fixture("empty_contents.jsonl", raw_dir)


@pytest.fixture
def fixture_thinking(raw_dir) -> Path:
    """Load the thinking_blocks fixture."""
    return load_fixture("thinking_blocks.jsonl", raw_dir)


@pytest.fixture
def fixture_errors(raw_dir) -> Path:
    """Load the error_results fixture."""
    return load_fixture("error_results.jsonl", raw_dir)


# --- Message builders for thinking blocks ---


def make_thinking_message(thinking: str, text: str) -> dict:
    """Create an assistant message with thinking and text."""
    return {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "thinking", "thinking": thinking},
                {"type": "text", "text": text},
            ]
        },
    }


# --- Sample data fixtures ---


@pytest.fixture
def sample_messages():
    """Return a set of sample messages for testing."""
    return [
        make_user_message("Hello, how are you?"),
        make_assistant_message("I'm doing well, thank you for asking!"),
        make_user_message("Can you help me with a task?"),
        make_tool_use("Read", {"file_path": "/tmp/test.txt"}),
        make_tool_result("File contents here"),
        make_assistant_message("I found the file contents."),
    ]


@pytest.fixture
def simple_transcript(raw_dir, sample_messages):
    """Create a simple transcript file and return its path."""
    path = raw_dir / "test-session.jsonl"
    write_transcript(path, sample_messages)
    return path
