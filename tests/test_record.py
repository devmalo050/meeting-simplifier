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
    assert set(p) == {"pid", "audio", "stop", "result", "log", "plugin_root", "ready"}
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


def test_stop_not_recording(record_mod):
    out = record_mod.cmd_stop([])
    assert out["ok"] is False
    assert "녹음 중이 아닙니다" in out["error"]


def test_stop_creates_flag_and_reports_duration(record_mod, tmp_path, monkeypatch):
    paths = record_mod.state_paths()
    audio = tmp_path / "rec.wav"
    _make_wav(audio, 2.0)
    paths["pid"].write_text("4242")
    paths["audio"].write_text(str(audio))
    monkeypatch.setattr(record_mod, "pid_alive", lambda pid: False)
    out = record_mod.cmd_stop([])
    assert out["ok"] is True
    assert abs(out["duration_seconds"] - 2.0) < 0.1
    assert not paths["pid"].exists()
    assert paths["stop"].exists() is False  # stop이 정리함


def test_stop_surfaces_worker_error(record_mod, tmp_path, monkeypatch):
    paths = record_mod.state_paths()
    paths["pid"].write_text("4242")
    paths["audio"].write_text(str(tmp_path / "rec.wav"))
    record_mod.report_error("마이크를 열 수 없습니다. ...")
    monkeypatch.setattr(record_mod, "pid_alive", lambda pid: False)
    out = record_mod.cmd_stop([])
    assert out["ok"] is False
    assert "마이크" in out["error"]


def test_worker_writes_ready_marker(record_mod, tmp_path, monkeypatch):
    _install_fake_sounddevice(monkeypatch)
    audio = tmp_path / "out.wav"
    paths = record_mod.state_paths()

    def trip_stop():
        time.sleep(0.5)
        paths["stop"].touch()

    threading.Thread(target=trip_stop, daemon=True).start()
    record_mod.run_worker(str(audio))
    assert paths["ready"].exists()


def test_worker_reports_error_on_missing_module(record_mod, tmp_path, monkeypatch):
    import json
    monkeypatch.setitem(sys.modules, "sounddevice", None)  # import 시 ImportError 유발
    rc = record_mod.run_worker(str(tmp_path / "out.wav"))
    assert rc == 1
    data = json.loads(record_mod.state_paths()["result"].read_text(encoding="utf-8"))
    assert data["ok"] is False


def test_start_fails_when_worker_dies_silently(record_mod, monkeypatch):
    def fake_spawn(audio_path):
        return 4242  # result/ready 미기록 + 죽은 pid (import 크래시 등 침묵 실패 모사)

    monkeypatch.setattr(record_mod, "spawn_worker", fake_spawn)
    monkeypatch.setattr(record_mod, "pid_alive", lambda pid: False)
    monkeypatch.setattr(record_mod, "START_PROBE_SECS", 0.3)
    out = record_mod.cmd_start([])
    assert out["ok"] is False
    paths = record_mod.state_paths()
    assert not paths["pid"].exists()


def test_start_succeeds_promptly_when_ready(record_mod, monkeypatch):
    def fake_spawn(audio_path):
        record_mod.state_paths()["ready"].write_text("1")
        return 4242

    monkeypatch.setattr(record_mod, "spawn_worker", fake_spawn)
    monkeypatch.setattr(record_mod, "pid_alive", lambda pid: True)
    t0 = time.time()
    out = record_mod.cmd_start([])
    assert out["ok"] is True
    assert time.time() - t0 < 1.0  # ready 마커로 START_PROBE_SECS(2초) 대기 없이 즉시 반환


def test_stop_handles_corrupt_pid(record_mod, tmp_path, monkeypatch):
    paths = record_mod.state_paths()
    audio = tmp_path / "rec.wav"
    _make_wav(audio, 1.0)
    paths["pid"].write_text("not-a-number")
    paths["audio"].write_text(str(audio))
    monkeypatch.setattr(record_mod, "STOP_WAIT_SECS", 0.2)
    out = record_mod.cmd_stop([])
    assert out["ok"] is True
    assert not paths["pid"].exists()
    assert paths["stop"].exists() is False


# --- json.loads 방어 테스트 ---

def test_start_corrupt_result_json_returns_error(record_mod, monkeypatch):
    def fake_spawn(audio_path):
        record_mod.state_paths()["result"].write_text("{broken json", encoding="utf-8")
        return 4242

    monkeypatch.setattr(record_mod, "spawn_worker", fake_spawn)
    monkeypatch.setattr(record_mod, "pid_alive", lambda pid: False)
    monkeypatch.setattr(record_mod, "START_PROBE_SECS", 0.3)
    out = record_mod.cmd_start([])
    assert out["ok"] is False
    assert "손상" in out["error"]


def test_stop_corrupt_result_json_returns_error(record_mod, tmp_path, monkeypatch):
    import json
    paths = record_mod.state_paths()
    audio = tmp_path / "rec.wav"
    _make_wav(audio, 1.0)
    paths["pid"].write_text("4242")
    paths["audio"].write_text(str(audio))
    paths["result"].write_text("{broken json", encoding="utf-8")
    monkeypatch.setattr(record_mod, "pid_alive", lambda pid: False)
    out = record_mod.cmd_stop([])
    assert out["ok"] is False
    assert "손상" in out["error"]


# --- wav_duration LIST 청크 테스트 ---

def _make_wav_with_list_chunk(path, seconds, rate=48000, list_extra_bytes=25000):
    import struct
    nframes = int(rate * seconds)
    sample_data = b"\x00\x00" * nframes
    list_payload = b"INFO" + b"ISFT" + struct.pack("<I", list_extra_bytes - 12) + b"A" * (list_extra_bytes - 12)
    list_chunk = b"LIST" + struct.pack("<I", len(list_payload)) + list_payload
    fmt_chunk = b"fmt " + struct.pack("<I", 16) + struct.pack("<HHIIHH", 1, 1, rate, rate * 2, 2, 16)
    data_chunk = b"data" + struct.pack("<I", len(sample_data)) + sample_data
    riff_body = b"WAVE" + fmt_chunk + list_chunk + data_chunk
    wav_bytes = b"RIFF" + struct.pack("<I", len(riff_body)) + riff_body
    with open(str(path), "wb") as f:
        f.write(wav_bytes)


def test_wav_duration_with_list_chunk(record_mod, tmp_path):
    p = tmp_path / "list.wav"
    _make_wav_with_list_chunk(p, 1.0)
    assert abs(record_mod.wav_duration(str(p)) - 1.0) < 0.05


# --- spawn_worker log FD close 테스트 ---

def test_spawn_worker_closes_log_fd(record_mod, tmp_path, monkeypatch):
    import subprocess
    closed = []
    opened = []

    class FakeFile:
        def close(self):
            closed.append(True)

    fake_file = FakeFile()

    def fake_open(path, mode):
        opened.append(path)
        return fake_file

    class FakeProc:
        pid = 9999

    def fake_popen(cmd, **kwargs):
        return FakeProc()

    monkeypatch.setattr(record_mod, "open", fake_open, raising=False)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    record_mod.spawn_worker("/tmp/fake.wav")
    assert len(closed) == 1, "log FD가 Popen 이후 close되지 않았음"


# --- force_kill 테스트 ---

def test_force_kill_uses_psutil_when_available(record_mod, monkeypatch):
    import types
    calls = []

    fake_psutil = types.ModuleType("psutil")

    class FakeProcess:
        def __init__(self, pid):
            calls.append(("init", pid))

        def terminate(self):
            calls.append(("terminate",))

        def wait(self, timeout):
            calls.append(("wait", timeout))

    class TimeoutExpired(Exception):
        pass

    fake_psutil.Process = FakeProcess
    fake_psutil.TimeoutExpired = TimeoutExpired
    monkeypatch.setitem(__import__("sys").modules, "psutil", fake_psutil)
    record_mod.force_kill(1234)
    assert ("init", 1234) in calls
    assert ("terminate",) in calls


def test_force_kill_falls_back_to_os_kill(record_mod, monkeypatch):
    import sys, types
    killed = []

    monkeypatch.setitem(sys.modules, "psutil", None)

    def fake_os_kill(pid, sig):
        killed.append((pid, sig))

    monkeypatch.setattr(record_mod.os, "kill", fake_os_kill)
    record_mod.force_kill(5678)
    assert (5678, 9) in killed


# --- main dispatch 테스트 ---

def test_main_no_args_returns_error(record_mod, monkeypatch, capsys):
    import json
    rc = record_mod.main([])
    assert rc == 2
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert "command required" in out["error"]


def test_main_unknown_command_returns_error(record_mod, monkeypatch, capsys):
    import json
    rc = record_mod.main(["badcmd"])
    assert rc == 2
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert "badcmd" in out["error"]
