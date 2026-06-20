import json
import os
import subprocess
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
REPO = SCRIPTS.parent


def _status(data_dir, path=None):
    env = dict(os.environ)
    env["MS_DATA_DIR"] = str(data_dir)
    if path is not None:
        env["PATH"] = path
    r = subprocess.run(
        ["bash", str(SCRIPTS / "lib_env.sh"), "status"],
        env=env, capture_output=True, text=True,
    )
    return r.stdout.strip()


def test_env_status_venv_pending(tmp_path):
    (tmp_path / "state").mkdir()
    assert _status(tmp_path) == "venv_pending"


def test_env_status_installing(tmp_path):
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "setup_status").write_text("installing_deps")
    assert _status(tmp_path) == "installing"


def test_env_status_deps_failed(tmp_path):
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "setup_status").write_text("failed:pip 설치 실패")
    assert _status(tmp_path) == "deps_failed"


def test_env_status_ready(tmp_path):
    (tmp_path / "state").mkdir()
    (tmp_path / ".venv").symlink_to(REPO / ".venv")
    assert _status(tmp_path) == "ready"


def test_install_python_present_when_python_exists():
    r = subprocess.run(
        ["bash", str(SCRIPTS / "install_python.sh")],
        capture_output=True, text=True,
    )
    data = json.loads(r.stdout)
    assert data["ok"] is True
    assert data["status"] == "python_present"
