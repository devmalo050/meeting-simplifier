import os
import sys
import threading
import time
import types
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


def _install_fake_sounddevice(monkeypatch, frames=b"\x00\x00" * 4800, fail=False):
    fake = types.ModuleType("sounddevice")

    def check_input_settings(**kwargs):
        if fail:
            raise RuntimeError("Unanticipated host error [PaErrorCode -9999]")

    class InputStream:
        def __init__(self, samplerate, channels, dtype, callback):
            self._cb = callback

        def __enter__(self):
            class _Arr:
                def tobytes(self_inner):
                    return frames
            self._cb(_Arr(), 4800, None, None)
            return self

        def __exit__(self, *a):
            return False

    fake.check_input_settings = check_input_settings
    fake.InputStream = InputStream
    monkeypatch.setitem(sys.modules, "sounddevice", fake)


def test_worker_writes_wav_until_stop(record_mod, tmp_path, monkeypatch):
    _install_fake_sounddevice(monkeypatch)
    audio = tmp_path / "out.wav"
    paths = record_mod.state_paths()

    def trip_stop():
        time.sleep(0.5)
        paths["stop"].touch()

    threading.Thread(target=trip_stop, daemon=True).start()
    rc = record_mod.run_worker(str(audio))
    assert rc == 0
    assert audio.exists()
    assert record_mod.wav_duration(str(audio)) > 0


def test_worker_reports_friendly_error_on_device_failure(record_mod, tmp_path, monkeypatch):
    import json
    _install_fake_sounddevice(monkeypatch, fail=True)
    rc = record_mod.run_worker(str(tmp_path / "out.wav"))
    assert rc == 1
    data = json.loads(record_mod.state_paths()["result"].read_text(encoding="utf-8"))
    assert data["ok"] is False
    assert "마이크" in data["error"]


def test_start_writes_pid_and_audio(record_mod, monkeypatch):
    spawned = {}

    def fake_spawn(audio_path):
        spawned["audio"] = audio_path
        return 4242

    monkeypatch.setattr(record_mod, "spawn_worker", fake_spawn)
    monkeypatch.setattr(record_mod, "pid_alive", lambda pid: True)
    monkeypatch.setattr(record_mod, "START_PROBE_SECS", 0.0)
    out = record_mod.cmd_start([])
    paths = record_mod.state_paths()
    assert out["ok"] is True
    assert paths["pid"].read_text().strip() == "4242"
    assert paths["audio"].read_text().strip() == spawned["audio"]


def test_start_refuses_when_already_recording(record_mod, monkeypatch):
    paths = record_mod.state_paths()
    paths["pid"].write_text("4242")
    monkeypatch.setattr(record_mod, "pid_alive", lambda pid: True)
    out = record_mod.cmd_start([])
    assert out["ok"] is False
    assert "이미 녹음" in out["error"]


def test_start_surfaces_worker_device_error(record_mod, monkeypatch):
    def fake_spawn(audio_path):
        record_mod.report_error("마이크를 열 수 없습니다. ...")
        return 4243

    monkeypatch.setattr(record_mod, "spawn_worker", fake_spawn)
    monkeypatch.setattr(record_mod, "pid_alive", lambda pid: False)
    monkeypatch.setattr(record_mod, "START_PROBE_SECS", 0.5)
    out = record_mod.cmd_start([])
    assert out["ok"] is False
    assert "마이크" in out["error"]
