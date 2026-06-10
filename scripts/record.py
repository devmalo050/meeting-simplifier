#!/usr/bin/env python3
import json
import os
import time
from pathlib import Path

SAMPLE_RATE = 48000
CHANNELS = 1
SAMPLE_WIDTH = 2
STOP_POLL_SECS = 0.2
START_PROBE_SECS = 2.0
STOP_WAIT_SECS = 10.0


def is_windows():
    return os.name == "nt"


def data_dir():
    env = os.environ.get("MS_DATA_DIR")
    if env:
        return Path(env)
    return Path.home() / ".claude" / "plugins" / "data" / "meeting-simplifier-meeting-simplifier"


def state_dir():
    d = data_dir() / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def state_paths():
    s = state_dir()
    return {
        "pid": s / "rec.pid",
        "audio": s / "audio_path",
        "stop": s / "stop.flag",
        "result": s / "result.json",
        "log": s / "worker.log",
        "plugin_root": s / "plugin_root",
    }


def venv_python(dd=None):
    venv = (dd or data_dir()) / ".venv"
    if is_windows():
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def friendly_device_error(exc):
    return (
        "마이크를 열 수 없습니다. Windows라면 [설정 > 개인정보 보호 및 보안 > 마이크]에서 "
        "'마이크 액세스', '앱이 마이크에 액세스하도록 허용', '데스크톱 앱이 마이크에 액세스하도록 허용'을 "
        "모두 켠 뒤 다시 시도하세요. macOS라면 [시스템 설정 > 개인정보 보호 및 보안 > 마이크]에서 "
        f"Claude(또는 터미널)를 허용하세요. (원본 오류: {exc})"
    )


def report_error(message):
    state_paths()["result"].write_text(
        json.dumps({"ok": False, "error": message}, ensure_ascii=False), encoding="utf-8"
    )
