import os
from pathlib import Path

DEFAULT_DATA_SUBPATH = Path(".claude") / "plugins" / "data" / "meeting-simplifier-meeting-simplifier"


def is_windows():
    return os.name == "nt"


def data_dir():
    env = os.environ.get("MS_DATA_DIR")
    if env:
        return Path(env)
    return Path.home() / DEFAULT_DATA_SUBPATH


def state_dir():
    d = data_dir() / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def venv_python(dd=None):
    venv = (dd or data_dir()) / ".venv"
    if is_windows():
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"
