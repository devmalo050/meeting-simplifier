#!/usr/bin/env python3
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
