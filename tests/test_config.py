import sys
import json
import subprocess
import importlib
from pathlib import Path
import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def config_mod(tmp_path, monkeypatch):
    monkeypatch.setenv("MS_DATA_DIR", str(tmp_path))
    import config
    importlib.reload(config)
    return config


def test_get_output_dir_none_when_unset(config_mod):
    assert config_mod.get_output_dir() is None


def test_effective_falls_back_to_default(config_mod):
    assert config_mod.effective_output_dir() == "~/Documents/meetings"


def test_set_then_get_roundtrip(config_mod, tmp_path):
    target = tmp_path / "회의록"
    resolved = config_mod.set_output_dir(str(target))
    assert resolved == str(target)
    assert config_mod.get_output_dir() == str(target)
    assert target.is_dir()


def test_set_expands_user(config_mod, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    resolved = config_mod.set_output_dir("~/Desktop/x")
    assert resolved == str(tmp_path / "Desktop" / "x")


def test_set_makes_relative_absolute(config_mod, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    resolved = config_mod.set_output_dir('sub/dir')
    assert Path(resolved).is_absolute()


def test_unset_reverts_to_none(config_mod, tmp_path):
    config_mod.set_output_dir(str(tmp_path / "a"))
    config_mod.unset_output_dir()
    assert config_mod.get_output_dir() is None


def test_load_config_survives_corrupt_json(config_mod):
    p = config_mod.config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{ broken", encoding="utf-8")
    assert config_mod.get_output_dir() is None


def test_unknown_keys_preserved(config_mod, tmp_path):
    config_mod.save_config({"whisper_model": "small"})
    config_mod.set_output_dir(str(tmp_path / "b"))
    cfg = config_mod.load_config()
    assert cfg["whisper_model"] == "small"
    assert "output_dir" in cfg


def _run_cli(tmp_path, *args):
    import os
    env = dict(os.environ)
    env["MS_DATA_DIR"] = str(tmp_path)
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "config.py"), *args],
        capture_output=True, text=True, env=env,
    )
    return r, json.loads(r.stdout)


def test_cli_show_default(tmp_path):
    r, out = _run_cli(tmp_path, "--show")
    assert r.returncode == 0
    assert out["ok"] is True
    assert out["is_default"] is True
    assert out["output_dir"] == "~/Documents/meetings"


def test_cli_set_then_show(tmp_path):
    target = str(tmp_path / "out")
    _run_cli(tmp_path, "--set", target)
    r, out = _run_cli(tmp_path, "--show")
    assert out["ok"] is True
    assert out["is_default"] is False
    assert out["output_dir"] == target


def test_cli_reset(tmp_path):
    _run_cli(tmp_path, "--set", str(tmp_path / "out"))
    r, out = _run_cli(tmp_path, "--reset")
    assert out["ok"] is True
    assert out["is_default"] is True
