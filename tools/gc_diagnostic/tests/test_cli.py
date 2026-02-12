import pytest
import subprocess
import os

@pytest.fixture
def mock_log_file(tmp_path, valid_healthy_log_content):
    file = tmp_path / "gc-memoryleak-fast.log"
    file.write_text(valid_healthy_log_content)
    return str(file)

def test_cli_rejects_invalid(mock_log_file):
    # But for invalid, mock an invalid file.
    invalid_file = mock_log_file.replace("gc-memoryleak-fast.log", "invalid.log")  # etc.
    # Use subprocess to run CLI.
    result = subprocess.run(["python", "tools/gc_diagnostic/get-gc-diagnostic.py", invalid_file], capture_output=True)
    assert result.returncode != 0
    assert "Invalid log format" in result.stderr.decode()

def test_cli_healthy_no_signal(mock_log_file):
    result = subprocess.run(["python", "tools/gc_diagnostic/get-gc-diagnostic.py", mock_log_file], capture_output=True)
    assert "NO STRONG SIGNAL" in result.stdout.decode()

# Add for --tail-window, --old-trend-mb-per-min, --format.