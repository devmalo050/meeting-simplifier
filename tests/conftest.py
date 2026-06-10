import sys
import importlib
from pathlib import Path
import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "data"
    d.mkdir()
    monkeypatch.setenv("MS_DATA_DIR", str(d))
    return d


@pytest.fixture
def record_mod(data_dir):
    import record
    importlib.reload(record)
    return record
