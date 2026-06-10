import os
from pathlib import Path


def test_data_dir_uses_env(record_mod, data_dir):
    assert record_mod.data_dir() == data_dir


def test_state_dir_is_created(record_mod, data_dir):
    s = record_mod.state_dir()
    assert s == data_dir / "state"
    assert s.is_dir()


def test_state_paths_keys(record_mod):
    p = record_mod.state_paths()
    assert set(p) == {"pid", "audio", "stop", "result", "log", "plugin_root"}
    assert p["stop"].name == "stop.flag"


def test_venv_python_posix(record_mod, data_dir, monkeypatch):
    monkeypatch.setattr(record_mod, "is_windows", lambda: False)
    assert record_mod.venv_python() == data_dir / ".venv" / "bin" / "python"


def test_venv_python_windows(record_mod, data_dir, monkeypatch):
    monkeypatch.setattr(record_mod, "is_windows", lambda: True)
    assert record_mod.venv_python() == data_dir / ".venv" / "Scripts" / "python.exe"
