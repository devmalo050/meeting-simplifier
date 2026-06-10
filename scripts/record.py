#!/usr/bin/env python3
import json
import os
import time
import wave
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


def wav_duration(path):
    try:
        with wave.open(path, "r") as f:
            params = f.getparams()
        file_size = os.path.getsize(path)
        frame_size = params.nchannels * params.sampwidth
        frames = max(0, (file_size - 44)) // frame_size
        return round(frames / params.framerate, 1)
    except Exception:
        return 0


def pid_alive(pid):
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def run_worker(audio_path):
    import sounddevice as sd
    paths = state_paths()
    try:
        sd.check_input_settings(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16")
    except Exception as e:
        report_error(friendly_device_error(e))
        return 1

    stop_flag = paths["stop"]
    wav = wave.open(audio_path, "wb")
    wav.setnchannels(CHANNELS)
    wav.setsampwidth(SAMPLE_WIDTH)
    wav.setframerate(SAMPLE_RATE)
    try:
        def callback(indata, frames, time_info, status):
            wav.writeframes(indata.tobytes())

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16", callback=callback):
            while not stop_flag.exists():
                time.sleep(STOP_POLL_SECS)
    except Exception as e:
        report_error(friendly_device_error(e))
        return 1
    finally:
        wav.close()
    return 0
