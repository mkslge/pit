from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path

import pytest

from helpers import pit_env, run


@pytest.fixture
def pit_command_env(tmp_path: Path) -> dict[str, str]:
    env = pit_env()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    pit_script = bin_dir / "pit"
    pit_script.write_text(
        "#!/bin/sh\n"
        f"PYTHONPATH={shlex.quote(env['PYTHONPATH'])} "
        f"exec {shlex.quote(sys.executable)} -m pit \"$@\"\n",
        encoding="utf-8",
    )
    pit_script.chmod(0o755)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    return env


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    return repo
