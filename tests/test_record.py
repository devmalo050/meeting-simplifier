import os
import wave
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


def test_friendly_device_error_has_korean_guidance(record_mod):
    msg = record_mod.friendly_device_error(Exception("Unanticipated host error [PaErrorCode -9999]"))
    assert "마이크" in msg
    assert "설정" in msg
    assert "-9999" in msg  # 원본 오류 보존


def test_report_error_writes_result(record_mod):
    import json
    record_mod.report_error("권한 오류")
    data = json.loads(record_mod.state_paths()["result"].read_text(encoding="utf-8"))
    assert data == {"ok": False, "error": "권한 오류"}


def _make_wav(path, seconds, rate=48000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))


def test_wav_duration(record_mod, tmp_path):
    p = tmp_path / "a.wav"
    _make_wav(p, 1.5)
    assert abs(record_mod.wav_duration(str(p)) - 1.5) < 0.05


def test_wav_duration_missing_file_returns_zero(record_mod, tmp_path):
    assert record_mod.wav_duration(str(tmp_path / "none.wav")) == 0


def test_pid_alive_for_current_process(record_mod):
    assert record_mod.pid_alive(os.getpid()) is True


def test_pid_alive_for_dead_pid(record_mod):
    assert record_mod.pid_alive(2147483600) is False
