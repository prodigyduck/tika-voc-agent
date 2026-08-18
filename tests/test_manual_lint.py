import subprocess
import sys


def test_메뉴얼_린트_통과():
    result = subprocess.run(
        [sys.executable, "scripts/lint_manual.py"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, "메뉴얼 린트 실패:\n" + result.stdout + result.stderr
