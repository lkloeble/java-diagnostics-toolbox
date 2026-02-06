# tools/gc_diagnostic/tests/conftest.py
from pathlib import Path
import pytest

@pytest.fixture(scope="session")
def gc_fast_log_lines():
    repo_root = Path(__file__).resolve().parents[3]  # remonte à java-diagnostics-toolbox
    path = repo_root / "samples" / "gc-memoryleak-fast.log"
    if not path.is_file():
        pytest.skip(f"Sample file not found: {path}\nAdd it to /samples/ and commit.")
    return path.read_text(encoding="utf-8").splitlines()