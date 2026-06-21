import importlib
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load(monkeypatch, tmp_path):
    monkeypatch.setenv("MS_DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "data").mkdir(exist_ok=True)
    import paths
    importlib.reload(paths)
    return paths


def test_data_dir_uses_env(monkeypatch, tmp_path):
    p = _load(monkeypatch, tmp_path)
    assert p.data_dir() == tmp_path / "data"


def test_data_dir_default_without_env(monkeypatch, tmp_path):
    monkeypatch.delenv("MS_DATA_DIR", raising=False)
    import paths
    importlib.reload(paths)
    assert paths.data_dir() == Path.home() / ".claude" / "plugins" / "data" / "meeting-simplifier-meeting-simplifier"


def test_state_dir_is_created(monkeypatch, tmp_path):
    p = _load(monkeypatch, tmp_path)
    s = p.state_dir()
    assert s == tmp_path / "data" / "state"
    assert s.is_dir()


def test_venv_python_posix(monkeypatch, tmp_path):
    p = _load(monkeypatch, tmp_path)
    monkeypatch.setattr(p, "is_windows", lambda: False)
    assert p.venv_python() == tmp_path / "data" / ".venv" / "bin" / "python"


def test_venv_python_windows(monkeypatch, tmp_path):
    p = _load(monkeypatch, tmp_path)
    monkeypatch.setattr(p, "is_windows", lambda: True)
    assert p.venv_python() == tmp_path / "data" / ".venv" / "Scripts" / "python.exe"
