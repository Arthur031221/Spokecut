import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_golden_files_match_the_python_implementation():
    """tests/js checks web/js against these files. If this fails, run scripts/make_golden.py and review the diff."""
    run = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "make_golden.py"), "--check"], capture_output=True, text=True
    )
    assert run.returncode == 0, run.stdout
