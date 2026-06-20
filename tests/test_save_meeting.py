import sys
import importlib
from pathlib import Path
import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def save_mod(tmp_path, monkeypatch):
    monkeypatch.setenv("MS_DATA_DIR", str(tmp_path))
    import config
    import save_meeting
    importlib.reload(config)
    importlib.reload(save_meeting)
    return save_meeting


def test_explicit_arg_wins(save_mod, tmp_path):
    import config
    config.set_output_dir(str(tmp_path / "cfg"))
    assert save_mod.resolve_output_dir("/explicit") == "/explicit"


def test_config_used_when_no_arg(save_mod, tmp_path):
    import config
    config.set_output_dir(str(tmp_path / "cfg"))
    assert save_mod.resolve_output_dir(None) == str(tmp_path / "cfg")


def test_default_when_nothing(save_mod):
    assert save_mod.resolve_output_dir(None) == "~/Documents/meetings"


def test_empty_string_falls_through_to_config(save_mod, tmp_path):
    import config
    config.set_output_dir(str(tmp_path / "cfg"))
    assert save_mod.resolve_output_dir("") == str(tmp_path / "cfg")
