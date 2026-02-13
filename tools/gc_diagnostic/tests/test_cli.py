import pytest
import subprocess
import sys
from pathlib import Path


@pytest.fixture
def mock_log_file(tmp_path, valid_healthy_log_content):
    file = tmp_path / "healthy.log"
    file.write_text(valid_healthy_log_content)
    return str(file)


@pytest.fixture
def invalid_log_file(tmp_path):
    file = tmp_path / "invalid.log"
    file.write_text("This is not a GC log file\nJust random text\n")
    return str(file)


def test_cli_rejects_invalid(invalid_log_file):
    """CLI should fail on invalid log format."""
    cli_path = Path(__file__).parent.parent / "get-gc-diagnostic.py"
    result = subprocess.run(
        [sys.executable, str(cli_path), invalid_log_file],
        capture_output=True
    )
    # Should exit with non-zero or show error
    assert result.returncode != 0 or b"Invalid" in result.stderr or b"Error" in result.stderr


def test_cli_healthy_no_signal(mock_log_file):
    """CLI should report NO STRONG SIGNAL for healthy log."""
    cli_path = Path(__file__).parent.parent / "get-gc-diagnostic.py"
    result = subprocess.run(
        [sys.executable, str(cli_path), mock_log_file],
        capture_output=True
    )
    assert result.returncode == 0
    assert b"NO STRONG SIGNAL" in result.stdout
