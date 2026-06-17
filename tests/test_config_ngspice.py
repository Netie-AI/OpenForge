"""Unit tests for ngspice command resolution and WSL path translation."""

from __future__ import annotations

import platform
from pathlib import Path

from openanalog.config import (
    ngspice_path_arg,
    probe_ngspice,
    resolve_ngspice_cmd,
    win_path_to_wsl,
)


def test_win_path_to_wsl():
    p = Path("C:/Users/user/OpenForge/OpenForge/tmp/test.sp")
    assert win_path_to_wsl(p) == "/mnt/c/Users/user/OpenForge/OpenForge/tmp/test.sp"


def test_ngspice_path_arg_wsl_prefix():
    cmd = ["wsl", "-d", "Ubuntu", "-e", "/usr/bin/ngspice"]
    p = Path("D:/data/deck.sp")
    assert ngspice_path_arg(p, cmd) == "/mnt/d/data/deck.sp"


def test_ngspice_path_arg_native():
    cmd = ["C:/msys64/mingw64/bin/ngspice.exe"]
    p = Path("C:/tmp/deck.sp")
    assert ngspice_path_arg(p, cmd) == str(p)


def test_resolve_ngspice_cmd_or_none():
    cmd = resolve_ngspice_cmd()
    if platform.system().lower() == "windows":
        assert cmd is None or cmd[0].lower().startswith("wsl") or "ngspice" in cmd[0].lower()
    else:
        assert cmd is None or "ngspice" in " ".join(cmd)


def test_probe_ngspice_when_available():
    cmd = resolve_ngspice_cmd()
    if cmd is None:
        ok, detail = probe_ngspice()
        assert not ok
        assert "not found" in detail
        return
    ok, detail = probe_ngspice()
    assert ok, detail
