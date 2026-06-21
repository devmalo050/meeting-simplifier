#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
import wave
from pathlib import Path

from paths import is_windows, data_dir, state_dir, venv_python

SAMPLE_RATE = 48000
CHANNELS = 1
SAMPLE_WIDTH = 2
STOP_POLL_SECS = 0.2
START_PROBE_SECS = 2.0
STOP_WAIT_SECS = 10.0


def state_paths():
    s = state_dir()
    return {
        "pid": s / "rec.pid",
        "audio": s / "audio_path",
        "stop": s / "stop.flag",
        "result": s / "result.json",
        "log": s / "worker.log",
        "plugin_root": s / "plugin_root",
        "ready": s / "ready.flag",
    }


def friendly_device_error(exc):
    if isinstance(exc, ModuleNotFoundError):
        return (
            f"녹음에 필요한 패키지가 아직 설치되지 않았습니다(missing: {exc.name}). "
            "플러그인 첫 설치/업데이트 직후라면 잠시 뒤 자동 설치가 끝납니다. "
            f"계속 실패하면 새 세션을 시작해 setup이 완료되게 하세요. (원본 오류: {exc})"
        )
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
            frames = f.getnframes()
            framerate = f.getframerate()
        return round(frames / framerate, 1)
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
    paths = state_paths()
    try:
        import sounddevice as sd
    except Exception as e:
        report_error(friendly_device_error(e))
        return 1
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
            paths["ready"].write_text("1")
            while not stop_flag.exists():
                time.sleep(STOP_POLL_SECS)
    except Exception as e:
        report_error(friendly_device_error(e))
        return 1
    finally:
        wav.close()
    return 0


def spawn_worker(audio_path):
    paths = state_paths()
    log = open(paths["log"], "ab")
    kwargs = dict(stdin=subprocess.DEVNULL, stdout=log, stderr=log)
    if is_windows():
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "_worker", audio_path], **kwargs
    )
    log.close()
    return proc.pid


def is_recording():
    paths = state_paths()
    if not paths["pid"].exists():
        return False
    try:
        return pid_alive(int(paths["pid"].read_text().strip()))
    except (ValueError, OSError):
        return False


def cmd_start(argv):
    paths = state_paths()
    if is_recording():
        return {"ok": False, "error": "이미 녹음 중입니다."}
    for key in ("stop", "result", "ready"):
        paths[key].unlink(missing_ok=True)
    audio_path = str(state_dir() / f"recording_{time.strftime('%Y%m%d_%H%M%S')}.wav")
    pid = spawn_worker(audio_path)
    paths["pid"].write_text(str(pid))
    paths["audio"].write_text(audio_path)

    deadline = time.time() + START_PROBE_SECS
    while time.time() < deadline:
        if paths["result"].exists():
            try:
                data = json.loads(paths["result"].read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {"ok": False, "error": "상태 파일이 손상되었습니다"}
            if data.get("ok") is False:
                for key in ("pid", "audio"):
                    paths[key].unlink(missing_ok=True)
                return data
            break
        if paths["ready"].exists():
            break
        if not pid_alive(pid):
            break
        time.sleep(STOP_POLL_SECS)

    # 워커가 ready도 result도 못 남기고 죽었으면 침묵 실패 — 거짓 성공 대신 명시적 에러
    if not paths["ready"].exists() and not pid_alive(pid) and not paths["result"].exists():
        for key in ("pid", "audio"):
            paths[key].unlink(missing_ok=True)
        tail = ""
        try:
            lines = paths["log"].read_text(encoding="utf-8", errors="replace").strip().splitlines()
            if lines:
                tail = " (로그: " + lines[-1][:200] + ")"
        except Exception:
            pass
        return {"ok": False, "error": "녹음 워커가 시작 직후 종료되었습니다. 환경 설치가 끝났는지 확인 후 다시 시도하세요." + tail}
    return {"ok": True, "audio_path": audio_path}


def force_kill(pid):
    try:
        import psutil
        p = psutil.Process(pid)
        p.terminate()
        try:
            p.wait(timeout=2)
        except psutil.TimeoutExpired:
            p.kill()
    except Exception:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


def cmd_stop(argv):
    paths = state_paths()
    if not paths["pid"].exists():
        return {"ok": False, "error": "녹음 중이 아닙니다."}
    try:
        pid = int(paths["pid"].read_text().strip())
    except ValueError:
        pid = None
    audio_path = paths["audio"].read_text().strip() if paths["audio"].exists() else ""

    paths["stop"].touch()
    if pid is not None:
        deadline = time.time() + STOP_WAIT_SECS
        while time.time() < deadline and pid_alive(pid):
            time.sleep(STOP_POLL_SECS)
        if pid_alive(pid):
            force_kill(pid)
    else:
        # pid 손상으로 종료 대상을 모르면, stop.flag를 즉시 지우지 말고
        # 워커가 플래그를 보고 자발 종료할 시간을 준다(고아 방지)
        time.sleep(min(STOP_WAIT_SECS, 1.0))

    for key in ("pid", "audio", "stop", "ready"):
        paths[key].unlink(missing_ok=True)

    if paths["result"].exists():
        try:
            data = json.loads(paths["result"].read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            paths["result"].unlink(missing_ok=True)
            return {"ok": False, "error": "상태 파일이 손상되었습니다"}
        paths["result"].unlink(missing_ok=True)
        if data.get("ok") is False:
            return data

    if not audio_path or not os.path.exists(audio_path):
        return {"ok": False, "error": "녹음 파일이 생성되지 않았습니다."}
    return {"ok": True, "audio_path": audio_path, "duration_seconds": wav_duration(audio_path)}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(json.dumps({"ok": False, "error": "command required"}, ensure_ascii=False))
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "_worker":
        return run_worker(rest[0])
    if cmd == "start":
        print(json.dumps(cmd_start(rest), ensure_ascii=False))
        return 0
    if cmd == "stop":
        print(json.dumps(cmd_stop(rest), ensure_ascii=False))
        return 0
    print(json.dumps({"ok": False, "error": f"unknown command: {cmd}"}, ensure_ascii=False))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
