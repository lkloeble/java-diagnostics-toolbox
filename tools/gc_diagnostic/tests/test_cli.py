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
    assert result.returncode == 0  # EXIT_HEALTHY
    assert b"NO STRONG SIGNAL" in result.stdout
    assert b"Exit code: 0 (HEALTHY)" in result.stdout


# === Exit code tests ===

def test_exit_code_healthy():
    """Test compute_exit_code returns 0 for no detections."""
    # Import here to avoid issues
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from importlib import import_module
    cli = import_module("get-gc-diagnostic")

    findings = {"suspects": [{"detected": False, "type": "retention_growth"}]}
    assert cli.compute_exit_code(findings) == 0


def test_exit_code_warning():
    """Test compute_exit_code returns 1 for non-critical detections."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from importlib import import_module
    cli = import_module("get-gc-diagnostic")

    findings = {"suspects": [
        {"detected": True, "type": "metaspace_leak", "confidence": "medium"}
    ]}
    assert cli.compute_exit_code(findings) == 1


def test_exit_code_critical_collector():
    """Test compute_exit_code returns 2 for Serial collector."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from importlib import import_module
    cli = import_module("get-gc-diagnostic")

    findings = {"suspects": [
        {"detected": True, "type": "collector_choice", "collector": "Serial"}
    ]}
    assert cli.compute_exit_code(findings) == 2


def test_exit_code_critical_retention():
    """Test compute_exit_code returns 2 for high confidence retention."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from importlib import import_module
    cli = import_module("get-gc-diagnostic")

    findings = {"suspects": [
        {"detected": True, "type": "retention_growth", "confidence": "high"}
    ]}
    assert cli.compute_exit_code(findings) == 2
