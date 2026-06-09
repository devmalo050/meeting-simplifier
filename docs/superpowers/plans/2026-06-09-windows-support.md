# 크로스플랫폼(Windows) 지원 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** macOS 전용 meeting-simplifier를 macOS CLI · macOS 데스크톱 앱 · Windows 데스크톱 앱 세 환경에서 동작하게 만든다.

**Architecture:** 녹음·프로세스 제어·변환·저장 로직을 OS 비의존 Python 코어(`scripts/record.py` 등)에 집약하고, 셸 스크립트(`.sh`)는 "venv python을 절대경로로 찾아 코어를 호출"하는 얇은 어댑터로 축소한다. 녹음은 SoX `rec`을 Python `sounddevice`로 교체하고, 백그라운드 워커는 stdin/stdout/stderr를 모두 끊고 새 프로세스 그룹으로 완전 detach해 데스크톱 앱 세션 hang(#43123)을 피한다.

**Tech Stack:** Python 3.9+, `sounddevice`(PortAudio 휠 번들), 표준 `wave`, `numpy`, `psutil`, `faster-whisper`(기존), `pytest`(신규 테스트), bash(macOS `sh` / Windows Git Bash).

**참조 스펙:** `docs/superpowers/specs/2026-06-09-windows-support-design.md`

> **셸 전략(중요):** Windows Claude Desktop 앱의 Code 탭은 Git for Windows 설치를 필수로 요구하므로 Git Bash가 보장된다. macOS CLI·데스크톱 앱도 `sh`/bash다. 따라서 세 타겟 모두 bash가 보장되어 **bash 단일 경로**로 구현한다(PowerShell 어댑터 없음). 셸은 OS 분기를 위해 `uname -s`(MINGW*/MSYS*/CYGWIN* → Windows)를 사용한다. hooks command 훅은 기본 셸(`sh`/Git Bash)로 실행되므로 `"shell"` 필드를 명시하지 않는다.

---

## 파일 구조

**신규**
- `scripts/record.py` — 녹음 코어. 경로/플랫폼 헬퍼(`is_windows`/`data_dir`/`state_dir`/`state_paths`/`venv_python`), 마이크 probe, WAV writer, 워커(녹음 루프+stop 폴링), start(detach spawn), stop(플래그+duration).
- `.gitattributes` — `*.sh text eol=lf`, `*.py text eol=lf`.
- `tests/test_record.py` — `record.py` 순수 로직 테스트.
- `tests/test_transcribe_paths.py` — `transcribe_server.py` 경로 헬퍼 테스트.
- `tests/conftest.py` — 공용 픽스처.
- `requirements-dev.txt` — 로컬 테스트 의존성.

**수정**
- `scripts/start_recording.sh`, `scripts/stop_recording.sh` — `record.py` 호출 어댑터로 축소.
- `scripts/transcribe.sh` — venv 절대경로 OS 분기.
- `scripts/setup.sh` — sox 제거, venv/Python/HF_HOME OS 분기.
- `scripts/transcribe_server.py` — `/tmp`→state 경로, HF_HOME(변환 로직 불변).
- `scripts/cleanup_old_versions.sh`, `scripts/uninstall.sh` — Windows 경로 보강.
- `hooks/hooks.json` — `</dev/null` 안전 detach, plugin_root 기록, SessionEnd venv 경로 OS 분기, POSIX `/tmp`·`pgrep`·`kill`·`seq` 제거.
- `commands/start.md`, `commands/stop.md`, `commands/summarize.md` — POSIX glob을 plugin_root 읽기+cache-glob 폴백으로, venv 경로 OS 분기.
- `README.md` — 3환경 지원, "Code 탭 + Local 세션", Git for Windows 필요, 마이크 권한.
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` — 버전 범프.

**상태 디렉토리 규약 (전 태스크 공통)**
- `DATA_DIR = $MS_DATA_DIR` 또는 `~/.claude/plugins/data/meeting-simplifier-meeting-simplifier`
- `STATE_DIR = DATA_DIR/state` — `rec.pid`, `audio_path`, `stop.flag`, `result.json`, `worker.log`, `plugin_root`
- `VENV = DATA_DIR/.venv` → python은 POSIX `bin/python`, Windows `Scripts/python.exe`
- `HF_HOME = DATA_DIR/hf`
- 녹음 파라미터: 48000Hz / mono / int16 (기존 SoX와 동일)
- 셸 OS 분기 관용구: `case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) ... ;; *) ... ;; esac`

---

## Task 1: 테스트 인프라 + 위생(.gitattributes, 셰뱅)

**Files:**
- Create: `requirements-dev.txt`, `tests/conftest.py`, `.gitattributes`
- Modify: `.gitignore`
- Modify (셰뱅): `scripts/setup.sh:1`, `scripts/start_recording.sh:1`, `scripts/stop_recording.sh:1`, `scripts/transcribe.sh:1`, `scripts/cleanup_old_versions.sh:1`, `scripts/uninstall.sh:1`

- [ ] **Step 1: `.gitattributes` 생성** — Windows 체크아웃 시 CRLF가 셰뱅을 깨뜨리는 것 방지

```gitattributes
*.sh text eol=lf
*.py text eol=lf
```

- [ ] **Step 2: 모든 `.sh` 셰뱅을 `#!/usr/bin/env bash`로 변경**

각 파일 1번째 줄 `#!/bin/bash` → `#!/usr/bin/env bash` (6개 파일: setup, start_recording, stop_recording, transcribe, cleanup_old_versions, uninstall).

- [ ] **Step 3: `requirements-dev.txt` 생성**

```
pytest>=8.0
sounddevice>=0.4.6
psutil>=5.9
numpy>=1.24
python-docx>=1.1
faster-whisper>=1.0
```

- [ ] **Step 4: 로컬 테스트 의존성 설치**

Run: `.venv/bin/python -m pip install -r requirements-dev.txt`
Expected: pytest, sounddevice, psutil, python-docx 설치 성공(numpy/faster-whisper는 이미 있음). (검증됨: Python 3.14.4 macOS arm64에서 sounddevice 0.5.5 universal2 / psutil 7.x abi3 / python-docx 1.2.0 / pytest 9.x 휠 설치 정상)

- [ ] **Step 5: `tests/conftest.py` 생성** — `record.py`를 import 가능하게 하고 `MS_DATA_DIR`를 임시 디렉토리로 격리

```python
import sys
import importlib
from pathlib import Path
import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "data"
    d.mkdir()
    monkeypatch.setenv("MS_DATA_DIR", str(d))
    return d


@pytest.fixture
def record_mod(data_dir):
    import record
    importlib.reload(record)
    return record
```

- [ ] **Step 6: `.gitignore`에 테스트 산출물 추가**

`.gitignore` 끝에 추가:
```
.pytest_cache/
tests/__pycache__/
```

- [ ] **Step 7: 빈 테스트로 pytest 동작 확인**

`tests/test_smoke.py` 임시 생성:
```python
def test_smoke():
    assert True
```
Run: `.venv/bin/python -m pytest tests/test_smoke.py -v`
Expected: PASS. 확인 후 `rm tests/test_smoke.py`.

- [ ] **Step 8: Commit**

```bash
git add .gitattributes requirements-dev.txt tests/conftest.py .gitignore scripts/*.sh
git commit -m "chore: 테스트 인프라 + 크로스플랫폼 위생(.gitattributes, env 셰뱅)"
```

---

## Task 2: `record.py` 경로/플랫폼 헬퍼 (TDD)

**Files:**
- Create: `scripts/record.py`
- Test: `tests/test_record.py`

> **주의(검증으로 확인된 함정):** OS 분기는 반드시 `is_windows()` 함수로 캡슐화한다. 테스트에서 `os.name`을 직접 monkeypatch하면 Python 3.14의 pathlib가 POSIX 호스트에서 `WindowsPath`를 생성하려다 `UnsupportedOperation: cannot instantiate 'WindowsPath'`로 깨진다. 테스트는 `is_windows`를 patch한다.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_record.py`

```python
import os
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
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_record.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'record'`

- [ ] **Step 3: `scripts/record.py` 최소 구현 (헬퍼만)**

```python
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
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_record.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/record.py tests/test_record.py
git commit -m "feat: record.py 경로/플랫폼 헬퍼 (data/state/venv 경로 is_windows 분기)"
```

---

## Task 3: 친절한 마이크 에러 변환 (TDD)

**Files:**
- Modify: `scripts/record.py`
- Test: `tests/test_record.py`

- [ ] **Step 1: 실패하는 테스트 추가** — `tests/test_record.py` 끝에

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_record.py -k "friendly or report" -v`
Expected: FAIL — `AttributeError: module 'record' has no attribute 'friendly_device_error'`

- [ ] **Step 3: 구현 추가** — `record.py`에 `import json` 추가하고 함수 정의

```python
import json


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
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_record.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/record.py tests/test_record.py
git commit -m "feat: record.py 마이크 권한 실패의 한국어 안내 변환 + result 파일 보고"
```

---

## Task 4: WAV duration + alive 헬퍼 (TDD)

**Files:**
- Modify: `scripts/record.py`
- Test: `tests/test_record.py`

- [ ] **Step 1: 실패하는 테스트 추가**

```python
import wave


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
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_record.py -k "wav_duration or pid_alive" -v`
Expected: FAIL — `AttributeError: ... 'wav_duration'`

- [ ] **Step 3: 구현 추가** — 파일 크기 기반 duration(헤더 nframes 불신), psutil 기반 alive. `record.py` 상단 import에 `import wave` 추가.

```python
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
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_record.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/record.py tests/test_record.py
git commit -m "feat: record.py WAV duration(파일크기 기반) + pid alive 헬퍼"
```

---

## Task 5: 녹음 워커 — 녹음 루프 + stop 폴링 (sounddevice 모킹)

**Files:**
- Modify: `scripts/record.py`
- Test: `tests/test_record.py`

워커는 sounddevice로 마이크를 열어 콜백마다 WAV에 프레임을 쓰고, `stop.flag`가 생기면 스트림을 닫고 종료한다. 테스트는 sounddevice를 가짜 모듈로 주입해 하드웨어 없이 검증한다.

- [ ] **Step 1: 실패하는 테스트 추가** — 가짜 sounddevice 주입

```python
import sys
import threading
import types


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
```

`time`은 `record.py`에서 import하지만 테스트에서도 쓰므로 `tests/test_record.py` 상단에 `import time`을 추가한다.

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_record.py -k worker -v`
Expected: FAIL — `AttributeError: ... 'run_worker'`

- [ ] **Step 3: `run_worker` 구현**

```python
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
```

> 주: 가짜 InputStream은 `__enter__`에서 콜백을 1회 호출(4800프레임=0.1초)하고 self를 반환하므로, with 블록 안 while 루프가 `trip_stop`이 0.5초 뒤 만든 `stop.flag`를 감지해 종료한다. `wav.close()`는 finally에서 호출되어 헤더가 정상 기록된다.

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_record.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/record.py tests/test_record.py
git commit -m "feat: record.py 녹음 워커(sounddevice 루프 + stop.flag 폴링 + 디바이스 실패 보고)"
```

---

## Task 6: start — 워커 완전 detach spawn (통합)

**Files:**
- Modify: `scripts/record.py`
- Test: `tests/test_record.py`

start는 (1) 이미 녹음 중인지 확인, (2) 이전 stop/result 정리, (3) 워커를 stdin/stdout/stderr 차단 + 새 프로세스 그룹으로 spawn, (4) PID/audio_path 기록, (5) 최대 `START_PROBE_SECS` 동안 워커가 마이크 실패(result.json)를 냈는지 확인, (6) JSON 출력.

- [ ] **Step 1: 실패하는 테스트 추가**

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_record.py -k start -v`
Expected: FAIL — `AttributeError: ... 'cmd_start'`

- [ ] **Step 3: 구현 추가** — `spawn_worker`(실제 detach) + `is_recording` + `cmd_start`. `record.py` 상단 import에 `import sys`, `import subprocess` 추가.

```python
import sys
import subprocess


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
    for key in ("stop", "result"):
        paths[key].unlink(missing_ok=True)
    audio_path = str(state_dir() / f"recording_{time.strftime('%Y%m%d_%H%M%S')}.wav")
    pid = spawn_worker(audio_path)
    paths["pid"].write_text(str(pid))
    paths["audio"].write_text(audio_path)

    deadline = time.time() + START_PROBE_SECS
    while time.time() < deadline:
        if paths["result"].exists():
            data = json.loads(paths["result"].read_text(encoding="utf-8"))
            if data.get("ok") is False:
                for key in ("pid", "audio"):
                    paths[key].unlink(missing_ok=True)
                return data
            break
        if not pid_alive(pid):
            break
        time.sleep(STOP_POLL_SECS)
    return {"ok": True, "audio_path": audio_path}
```

> `subprocess.DETACHED_PROCESS`/`CREATE_NO_WINDOW`는 Windows에만 존재하므로 `is_windows()` 분기 안에서만 접근한다(POSIX에서 `AttributeError` 없음).

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_record.py -v`
Expected: 16 passed

- [ ] **Step 5: 실제 detach 수동 검증(macOS)** — 워커가 stdin/stdout을 물지 않는지

Run:
```bash
mkdir -p /tmp/ms-test/state
MS_DATA_DIR=/tmp/ms-test .venv/bin/python scripts/record.py _worker /tmp/ms-test/x.wav </dev/null >/tmp/ms-test/w.log 2>&1 &
sleep 1; touch /tmp/ms-test/state/stop.flag; sleep 1
ls -la /tmp/ms-test/x.wav 2>/dev/null; cat /tmp/ms-test/state/result.json 2>/dev/null; rm -rf /tmp/ms-test
```
Expected: `x.wav` 생성(권한 허용 시) 또는 `result.json`에 마이크 안내. 명령이 즉시 반환되고 셸이 hang되지 않음.

- [ ] **Step 6: Commit**

```bash
git add scripts/record.py tests/test_record.py
git commit -m "feat: record.py start — 워커 완전 detach spawn + 마이크 실패 조기 surface"
```

---

## Task 7: stop — 플래그 종료 + duration (통합)

**Files:**
- Modify: `scripts/record.py`
- Test: `tests/test_record.py`

stop은 (1) 녹음 중 아니면 에러, (2) `stop.flag` 생성, (3) 워커가 죽을 때까지 `STOP_WAIT_SECS` 대기, (4) 미응답 시 강제 종료, (5) 워커가 남긴 result 에러 확인, (6) duration 계산해 JSON. `main()` 디스패처도 이 태스크에서 추가한다.

- [ ] **Step 1: 실패하는 테스트 추가**

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_record.py -k stop -v`
Expected: FAIL — `AttributeError: ... 'cmd_stop'`

- [ ] **Step 3: 구현 추가** — `force_kill`, `cmd_stop`, `main`

```python
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

    for key in ("pid", "audio", "stop"):
        paths[key].unlink(missing_ok=True)

    if paths["result"].exists():
        data = json.loads(paths["result"].read_text(encoding="utf-8"))
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
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_record.py -v`
Expected: 19 passed

- [ ] **Step 5: end-to-end 수동 검증(macOS, 마이크 허용 환경)**

Run:
```bash
export MS_DATA_DIR=/tmp/ms-e2e; mkdir -p /tmp/ms-e2e/state
.venv/bin/python scripts/record.py start
sleep 3
.venv/bin/python scripts/record.py stop
rm -rf /tmp/ms-e2e; unset MS_DATA_DIR
```
Expected: start가 `{"ok": true, "audio_path": ...}`, stop이 `{"ok": true, ..., "duration_seconds": ~3.0}` 출력. 마이크 미허용 시 start가 한국어 안내를 반환.

- [ ] **Step 6: Commit**

```bash
git add scripts/record.py tests/test_record.py
git commit -m "feat: record.py stop(플래그 종료 + duration + 강제종료 fallback) + main 디스패처"
```

---

## Task 8: `transcribe_server.py` 경로 크로스플랫폼화

**Files:**
- Modify: `scripts/transcribe_server.py`(import 부근 + main의 out_dir)
- Test: `tests/test_transcribe_paths.py`

`/tmp/meeting-simplifier` 하드코딩을 state 디렉토리로 교체한다. 변환 로직(faster-whisper, 청크 분할)은 변경하지 않는다.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_transcribe_paths.py`

```python
import sys
import importlib
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def test_transcript_out_dir_uses_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("MS_DATA_DIR", str(tmp_path))
    import transcribe_server
    importlib.reload(transcribe_server)
    out = transcribe_server.transcript_out_dir()
    assert Path(out) == tmp_path / "state"
    assert Path(out).is_dir()
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_transcribe_paths.py -v`
Expected: FAIL — `AttributeError: ... 'transcript_out_dir'`

- [ ] **Step 3: 구현** — `transcribe_server.py` 상단(import 뒤)에 헬퍼 추가

```python
def transcript_out_dir():
    base = os.environ.get("MS_DATA_DIR") or os.path.join(
        os.path.expanduser("~"), ".claude", "plugins", "data", "meeting-simplifier-meeting-simplifier"
    )
    out = os.path.join(base, "state")
    os.makedirs(out, exist_ok=True)
    return out
```

`main()` 안 `out_dir = "/tmp/meeting-simplifier"`(149행 부근)를 다음으로 교체:
```python
            out_dir = transcript_out_dir()
```
(바로 다음 줄 `os.makedirs(out_dir, exist_ok=True)`는 헬퍼가 이미 만들므로 남겨도 무해 — 그대로 둔다.)

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_transcribe_paths.py -v`
Expected: 1 passed

- [ ] **Step 5: 변환 회귀 확인(짧은 wav)**

Run:
```bash
.venv/bin/python -c "import wave; w=wave.open('/tmp/t.wav','wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(b'\x00\x00'*16000); w.close()"
MS_DATA_DIR=/tmp/ms-tx .venv/bin/python scripts/transcribe_server.py --oneshot /tmp/t.wav
rm -rf /tmp/ms-tx /tmp/t.wav
```
Expected: `{"transcript": "", "language": ...}` JSON, transcript_file 경로가 `/tmp/ms-tx/state/` 하위.

- [ ] **Step 6: Commit**

```bash
git add scripts/transcribe_server.py tests/test_transcribe_paths.py
git commit -m "feat: transcribe_server.py /tmp 제거 → data/state 경로 크로스플랫폼화"
```

---

## Task 9: `setup.sh` 크로스플랫폼화 (sox 제거, venv/Python/HF_HOME 분기)

**Files:**
- Modify: `scripts/setup.sh`

SoX 설치 블록 제거, Python 탐색 OS별, venv python 경로 OS 분기, sounddevice/psutil 추가, HF_HOME을 data 디렉토리로 고정, 모델 캐시 검사를 HF_HOME 기준으로. python-docx는 best-effort(실패해도 setup 성공).

- [ ] **Step 1: `setup.sh` 전체 교체**

```bash
#!/usr/bin/env bash
# scripts/setup.sh — venv + faster-whisper + sounddevice 자동 설치 (POSIX/Git Bash)

DATA_DIR="${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}"
LOCK_FILE="$DATA_DIR/setup.lock"
mkdir -p "$DATA_DIR"

if [ -f "$LOCK_FILE" ]; then
  LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null)
  if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
    exit 0
  fi
fi
trap 'rm -f "$LOCK_FILE"' EXIT
echo $$ > "$LOCK_FILE"

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) IS_WIN=1 ;;
  *) IS_WIN=0 ;;
esac

if [ "$IS_WIN" = "1" ]; then CANDIDATES="py python python3"; else CANDIDATES="python3 python"; fi
PYTHON_CMD=""
for cmd in $CANDIDATES; do
  if command -v "$cmd" &>/dev/null; then PYTHON_CMD="$cmd"; break; fi
done
if [ -z "$PYTHON_CMD" ]; then
  echo "⚠️  Python이 없습니다. Windows: winget install -e --id Python.Python.3.12 / macOS: brew install python"
  exit 1
fi

PY_OK=$("$PYTHON_CMD" -c "import sys; print(1 if sys.version_info[:2] >= (3,9) else 0)" 2>/dev/null)
if [ "$PY_OK" != "1" ]; then
  echo "⚠️  Python 3.9 이상이 필요합니다."
  exit 1
fi

VENV_DIR="$DATA_DIR/.venv"
if [ "$IS_WIN" = "1" ]; then VENV_PYTHON="$VENV_DIR/Scripts/python.exe"; else VENV_PYTHON="$VENV_DIR/bin/python"; fi

if [ ! -f "$VENV_PYTHON" ]; then
  echo "📦 Python 가상환경을 생성합니다..."
  "$PYTHON_CMD" -m venv "$VENV_DIR" || { echo "❌ venv 생성 실패"; exit 1; }
fi

if ! "$VENV_PYTHON" -c "import faster_whisper, sounddevice, psutil" 2>/dev/null; then
  echo "📦 핵심 의존성을 설치합니다 (faster-whisper, sounddevice, psutil)..."
  "$VENV_PYTHON" -m pip install --quiet faster-whisper sounddevice psutil \
    || { echo "❌ 핵심 의존성 설치 실패. 수동: pip install faster-whisper sounddevice psutil"; exit 1; }
fi

if ! "$VENV_PYTHON" -c "import docx" 2>/dev/null; then
  "$VENV_PYTHON" -m pip install --quiet python-docx \
    && echo "✅ python-docx 설치 완료" || echo "⚠️  python-docx 설치 실패 (docx 출력만 영향, md/txt는 정상)"
fi

export HF_HOME="$DATA_DIR/hf"
WHISPER_MODEL="${WHISPER_MODEL:-medium}"
MODEL_CACHE="$HF_HOME/hub/models--Systran--faster-whisper-${WHISPER_MODEL}"
if [ ! -d "$MODEL_CACHE" ]; then
  echo "📦 Whisper ${WHISPER_MODEL} 모델을 다운로드합니다 (최초 1회)..."
  HF_HOME="$HF_HOME" "$VENV_PYTHON" -c "from faster_whisper import WhisperModel; WhisperModel('${WHISPER_MODEL}', device='cpu', compute_type='int8')" 2>/dev/null \
    && echo "✅ 모델 준비 완료" || echo "⚠️  모델 다운로드 실패 (첫 변환 시 자동 시도)"
fi

if [ -n "$MS_SETUP_MARKER" ] && "$VENV_PYTHON" -c "import faster_whisper, sounddevice" 2>/dev/null; then
  touch "$MS_SETUP_MARKER"
fi
```

- [ ] **Step 2: 문법 확인**

Run: `bash -n scripts/setup.sh`
Expected: 출력 없음(문법 정상).

- [ ] **Step 3: macOS 실행 검증(임시 data 디렉토리, tiny 모델로 빠르게)**

Run:
```bash
MS_DATA_DIR=/tmp/ms-setup MS_SETUP_MARKER=/tmp/ms-setup/.done WHISPER_MODEL=tiny bash scripts/setup.sh
/tmp/ms-setup/.venv/bin/python -c "import sounddevice, psutil, faster_whisper; print('ok')"
ls /tmp/ms-setup/.done && rm -rf /tmp/ms-setup
```
Expected: `ok` 출력 + `.done` 마커 생성.

- [ ] **Step 4: Commit**

```bash
git add scripts/setup.sh
git commit -m "feat: setup.sh 크로스플랫폼화 — sox 제거, sounddevice/psutil 추가, venv/Python/HF_HOME OS 분기"
```

---

## Task 10: `transcribe.sh` + 녹음 셸 어댑터 축소

**Files:**
- Modify: `scripts/transcribe.sh`, `scripts/start_recording.sh`, `scripts/stop_recording.sh`

세 스크립트를 "venv python을 OS 분기 절대경로로 찾아 코어를 호출"하는 얇은 어댑터로 만든다. POSIX 의존(`rec`, `pgrep`, `kill`, `/tmp`, `seq`) 전부 제거.

- [ ] **Step 1: `transcribe.sh` 교체**

```bash
#!/usr/bin/env bash
# scripts/transcribe.sh — 오디오 → 텍스트 (record.py와 동일 venv 사용)
PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AUDIO_PATH="$1"
DATA_DIR="${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}"
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) VENV_PYTHON="$DATA_DIR/.venv/Scripts/python.exe" ;;
  *) VENV_PYTHON="$DATA_DIR/.venv/bin/python" ;;
esac

if [ -z "$AUDIO_PATH" ]; then echo '{"error": "audio_path가 필요합니다."}'; exit 1; fi
if [ ! -f "$AUDIO_PATH" ]; then echo "{\"error\": \"파일이 없습니다: $AUDIO_PATH\"}"; exit 1; fi
if [ ! -f "$VENV_PYTHON" ] || ! "$VENV_PYTHON" -c "import faster_whisper" 2>/dev/null; then
  echo '{"error": "환경이 아직 준비되지 않았습니다. 의존성 설치가 끝난 뒤 다시 시도하세요."}'; exit 1
fi

export HF_HOME="$DATA_DIR/hf"
WHISPER_MODEL="${WHISPER_MODEL:-medium}" HF_HOME="$HF_HOME" "$VENV_PYTHON" \
  "$PLUGIN_ROOT/scripts/transcribe_server.py" --oneshot "$AUDIO_PATH"
```

- [ ] **Step 2: `start_recording.sh` 교체**

```bash
#!/usr/bin/env bash
# scripts/start_recording.sh — record.py start 어댑터
PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}"
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) VENV_PYTHON="$DATA_DIR/.venv/Scripts/python.exe" ;;
  *) VENV_PYTHON="$DATA_DIR/.venv/bin/python" ;;
esac
if [ ! -f "$VENV_PYTHON" ]; then
  echo '{"ok": false, "error": "환경이 아직 준비되지 않았습니다. 잠시 후 다시 시도하세요."}'; exit 0
fi
"$VENV_PYTHON" "$PLUGIN_ROOT/scripts/record.py" start </dev/null
```

- [ ] **Step 3: `stop_recording.sh` 교체**

```bash
#!/usr/bin/env bash
# scripts/stop_recording.sh — record.py stop 어댑터
PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}"
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) VENV_PYTHON="$DATA_DIR/.venv/Scripts/python.exe" ;;
  *) VENV_PYTHON="$DATA_DIR/.venv/bin/python" ;;
esac
if [ ! -f "$VENV_PYTHON" ]; then
  echo '{"ok": false, "error": "환경이 아직 준비되지 않았습니다."}'; exit 0
fi
"$VENV_PYTHON" "$PLUGIN_ROOT/scripts/record.py" stop </dev/null
```

- [ ] **Step 4: 문법 + 어댑터 동작 확인**

Run:
```bash
bash -n scripts/transcribe.sh scripts/start_recording.sh scripts/stop_recording.sh
MS_DATA_DIR=/tmp/ms-ad bash scripts/start_recording.sh
rm -rf /tmp/ms-ad
```
Expected: 문법 정상, start 어댑터가 `{"ok": false, "error": "환경이 아직 준비되지 않았습니다. ..."}` 반환(venv 없으므로).

- [ ] **Step 5: Commit**

```bash
git add scripts/transcribe.sh scripts/start_recording.sh scripts/stop_recording.sh
git commit -m "refactor: 녹음/변환 셸을 record.py 호출 얇은 어댑터로 축소 (POSIX 의존 제거)"
```

---

## Task 11: `hooks.json` — 안전 detach + plugin_root 기록 + SessionEnd 정리

**Files:**
- Modify: `hooks/hooks.json`

SessionStart는 (1) plugin_root를 state에 기록, (2) cleanup, (3) setup을 **stdin까지 끊고**(`</dev/null`) 백그라운드 실행. SessionEnd는 record.py stop으로 워커 정리(venv 경로 OS 분기). `/tmp`·`pgrep`·`kill`·`seq` 제거. hook command는 기본 셸(`sh`/Git Bash)로 실행되므로 `"shell"` 필드는 쓰지 않는다.

- [ ] **Step 1: `hooks/hooks.json` 교체**

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "DATA_DIR=\"${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}\"; mkdir -p \"$DATA_DIR/state\"; printf '%s' \"${CLAUDE_PLUGIN_ROOT}\" > \"$DATA_DIR/state/plugin_root\"; bash \"${CLAUDE_PLUGIN_ROOT}/scripts/cleanup_old_versions.sh\" >>\"$DATA_DIR/cleanup.log\" 2>&1; if [ ! -f \"$DATA_DIR/.setup-complete\" ]; then MS_SETUP_MARKER=\"$DATA_DIR/.setup-complete\" nohup bash \"${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh\" </dev/null >\"$DATA_DIR/setup.log\" 2>&1 & fi"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "DATA_DIR=\"${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}\"; case \"$(uname -s)\" in MINGW*|MSYS*|CYGWIN*) VP=\"$DATA_DIR/.venv/Scripts/python.exe\";; *) VP=\"$DATA_DIR/.venv/bin/python\";; esac; if [ -f \"$VP\" ] && [ -f \"$DATA_DIR/state/rec.pid\" ]; then \"$VP\" \"${CLAUDE_PLUGIN_ROOT}/scripts/record.py\" stop </dev/null >/dev/null 2>&1 || true; fi"
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 2: JSON 유효성 확인**

Run: `.venv/bin/python -c "import json; json.load(open('hooks/hooks.json')); print('json ok')"`
Expected: `json ok`

- [ ] **Step 3: SessionStart 인라인 실행 검증** — plugin_root 기록 + setup 백그라운드 시작이 hang 없이 즉시 반환되는지

Run:
```bash
export CLAUDE_PLUGIN_ROOT="$(pwd)" MS_DATA_DIR=/tmp/ms-hook
DATA_DIR="$MS_DATA_DIR"; mkdir -p "$DATA_DIR/state"; printf '%s' "$CLAUDE_PLUGIN_ROOT" > "$DATA_DIR/state/plugin_root"
time ( if [ ! -f "$DATA_DIR/.setup-complete" ]; then MS_SETUP_MARKER="$DATA_DIR/.setup-complete" nohup bash "$CLAUDE_PLUGIN_ROOT/scripts/setup.sh" </dev/null >"$DATA_DIR/setup.log" 2>&1 & fi )
echo "plugin_root=[$(cat "$DATA_DIR/state/plugin_root")]"
sleep 1; rm -rf /tmp/ms-hook; unset CLAUDE_PLUGIN_ROOT MS_DATA_DIR
```
Expected: `time`이 1초 미만(백그라운드라 즉시 반환), plugin_root에 현재 경로 기록, 셸 hang 없음.

- [ ] **Step 4: Commit**

```bash
git add hooks/hooks.json
git commit -m "feat: hooks.json 안전 detach(</dev/null) + plugin_root 기록 + SessionEnd venv OS 분기"
```

---

## Task 12: `commands/*.md` — glob→plugin_root(+폴백), venv 경로 OS 분기

**Files:**
- Modify: `commands/start.md`, `commands/stop.md`, `commands/summarize.md`

POSIX glob을 plugin_root 읽기로 바꾸되, **cache-glob 폴백을 복원**한다(SessionStart 훅은 새 세션에서만 발동하므로, 설치/업데이트 직후 같은 세션에서 plugin_root 파일이 아직 없을 수 있음 — 메모리 `feedback_hook_lifecycle`). save_meeting/transcribe 호출의 venv 경로는 `uname` 분기한다. 셸은 bash 단일(Git Bash/sh).

공통 PLUGIN_DIR 해석 관용구(모든 bash 블록에서 사용):
```bash
DATA_DIR="${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}"
PLUGIN_DIR="$(cat "$DATA_DIR/state/plugin_root" 2>/dev/null)"
[ -z "$PLUGIN_DIR" ] && PLUGIN_DIR="$(ls -d ~/.claude/plugins/cache/*/meeting-simplifier/*/ 2>/dev/null | sort -V | tail -1)"
[ -z "$PLUGIN_DIR" ] && PLUGIN_DIR=~/.claude/plugins/marketplaces/meeting-simplifier
PLUGIN_DIR="${PLUGIN_DIR%/}"
```

- [ ] **Step 1: `commands/start.md` 본문 교체** (frontmatter 유지)

frontmatter 아래 본문 전체를 교체:

````markdown
Bash 도구로 녹음을 시작하세요:

```bash
DATA_DIR="${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}"
PLUGIN_DIR="$(cat "$DATA_DIR/state/plugin_root" 2>/dev/null)"
[ -z "$PLUGIN_DIR" ] && PLUGIN_DIR="$(ls -d ~/.claude/plugins/cache/*/meeting-simplifier/*/ 2>/dev/null | sort -V | tail -1)"
[ -z "$PLUGIN_DIR" ] && PLUGIN_DIR=~/.claude/plugins/marketplaces/meeting-simplifier
PLUGIN_DIR="${PLUGIN_DIR%/}"
bash "$PLUGIN_DIR/scripts/start_recording.sh"
```

결과 JSON을 파싱합니다:
- `"ok": true` → "녹음을 시작했습니다. 회의가 끝나면 '녹음 끝' 또는 '회의록 만들어줘' 라고 말씀해주세요."
- `"ok": false` → `error` 값을 사용자에게 그대로 전달하세요. (마이크 권한 안내가 포함될 수 있습니다.)
````

- [ ] **Step 2: `commands/stop.md` 1·2·5단계 bash 블록 교체** (3·4·6단계 회의록 규칙/템플릿/완료 안내는 유지)

1단계(녹음 중지) bash 블록:
```bash
DATA_DIR="${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}"
PLUGIN_DIR="$(cat "$DATA_DIR/state/plugin_root" 2>/dev/null)"
[ -z "$PLUGIN_DIR" ] && PLUGIN_DIR="$(ls -d ~/.claude/plugins/cache/*/meeting-simplifier/*/ 2>/dev/null | sort -V | tail -1)"
[ -z "$PLUGIN_DIR" ] && PLUGIN_DIR=~/.claude/plugins/marketplaces/meeting-simplifier
PLUGIN_DIR="${PLUGIN_DIR%/}"
bash "$PLUGIN_DIR/scripts/stop_recording.sh"
```

2단계(텍스트 변환) bash 블록:
```bash
DATA_DIR="${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}"
PLUGIN_DIR="$(cat "$DATA_DIR/state/plugin_root" 2>/dev/null)"
[ -z "$PLUGIN_DIR" ] && PLUGIN_DIR="$(ls -d ~/.claude/plugins/cache/*/meeting-simplifier/*/ 2>/dev/null | sort -V | tail -1)"
[ -z "$PLUGIN_DIR" ] && PLUGIN_DIR=~/.claude/plugins/marketplaces/meeting-simplifier
PLUGIN_DIR="${PLUGIN_DIR%/}"
bash "$PLUGIN_DIR/scripts/transcribe.sh" "<1단계 audio_path>"
```

5단계(회의록 저장) bash 블록 — venv 경로 OS 분기 포함:
```bash
DATA_DIR="${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}"
PLUGIN_DIR="$(cat "$DATA_DIR/state/plugin_root" 2>/dev/null)"
[ -z "$PLUGIN_DIR" ] && PLUGIN_DIR="$(ls -d ~/.claude/plugins/cache/*/meeting-simplifier/*/ 2>/dev/null | sort -V | tail -1)"
[ -z "$PLUGIN_DIR" ] && PLUGIN_DIR=~/.claude/plugins/marketplaces/meeting-simplifier
PLUGIN_DIR="${PLUGIN_DIR%/}"
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) VENV_PY="$DATA_DIR/.venv/Scripts/python.exe";; *) VENV_PY="$DATA_DIR/.venv/bin/python";; esac
MINUTES_FILE=$(mktemp 2>/dev/null || echo "$DATA_DIR/state/minutes.md")
cat > "$MINUTES_FILE" << 'MINUTES_EOF'
{회의록 내용}
MINUTES_EOF
"$VENV_PY" "$PLUGIN_DIR/scripts/save_meeting.py" \
  --title "{회의 제목}" --minutes-file "$MINUTES_FILE" \
  --audio-path "{1단계 audio_path}" --transcript-file "{2단계 transcript_file}"
rm -f "$MINUTES_FILE"
```

- [ ] **Step 3: `commands/summarize.md` 오디오 변환 bash 블록 교체**

오디오 파일 변환 블록:
```bash
DATA_DIR="${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}"
PLUGIN_DIR="$(cat "$DATA_DIR/state/plugin_root" 2>/dev/null)"
[ -z "$PLUGIN_DIR" ] && PLUGIN_DIR="$(ls -d ~/.claude/plugins/cache/*/meeting-simplifier/*/ 2>/dev/null | sort -V | tail -1)"
[ -z "$PLUGIN_DIR" ] && PLUGIN_DIR=~/.claude/plugins/marketplaces/meeting-simplifier
PLUGIN_DIR="${PLUGIN_DIR%/}"
bash "$PLUGIN_DIR/scripts/transcribe.sh" "<file_path>"
```
텍스트 파일(`cat "<file_path>"`)과 stop.md 3~6단계 참조 안내는 유지한다.

- [ ] **Step 4: glob 잔재 제거 확인**

Run: `grep -l "plugin_root" commands/*.md; echo "---"; grep -c "ls -d ~/.claude/plugins/cache" commands/*.md`
Expected: 세 파일 모두 plugin_root 포함. cache-glob은 폴백으로만 등장(start=1, stop=3, summarize=1).

- [ ] **Step 5: Commit**

```bash
git add commands/start.md commands/stop.md commands/summarize.md
git commit -m "feat: 커맨드 PLUGIN_DIR을 plugin_root+cache-glob 폴백으로, venv 경로 OS 분기"
```

---

## Task 13: cleanup/uninstall 크로스플랫폼 보강

**Files:**
- Modify: `scripts/cleanup_old_versions.sh`, `scripts/uninstall.sh`

`uninstall.sh`의 HF 캐시 경로를 HF_HOME(data/hf) 기준으로 갱신하고 `/tmp` 잔재 제거 줄을 삭제한다(data 전체 삭제가 state를 포함). `cleanup_old_versions.sh`는 Git Bash에서도 동일 경로로 동작하므로 주석만 보강.

- [ ] **Step 1: `uninstall.sh`의 HF 모델 캐시 경로 갱신**

기존 23–25행(`for d in "$HOME"/.cache/huggingface/hub/models--Systran--faster-whisper-*`) 블록을 다음으로 교체:
```bash
DATA_DIR="${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}"
for d in "$DATA_DIR"/hf/hub/models--Systran--faster-whisper-* "$HOME"/.cache/huggingface/hub/models--Systran--faster-whisper-*; do
  [ -e "$d" ] && remove "$d" "Whisper 모델 캐시"
done
```

- [ ] **Step 2: `uninstall.sh`의 `/tmp` 상태 디렉토리 제거 줄 삭제**

28행 `remove "/tmp/meeting-simplifier" "런타임 상태 디렉토리"`를 **삭제**한다(별도 state remove 추가 불필요 — 35행 `remove "$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier" ...`가 state를 포함). 같은 맥락의 `/tmp/meeting-simplifier-setup.lock`·`/tmp/warmup-*.wav` 제거 줄도 더 이상 생성되지 않는 산출물이므로 삭제한다.

- [ ] **Step 3: `cleanup_old_versions.sh` 주석 보강**

`case "$PARENT" in`(31행 부근) 바로 위에 한 줄 추가:
```bash
# Git Bash(Windows)에서도 동일 경로($HOME/.claude/plugins/cache/...)로 매칭되어 동작한다.
```

- [ ] **Step 4: 문법 확인**

Run: `bash -n scripts/uninstall.sh scripts/cleanup_old_versions.sh`
Expected: 문법 정상. (uninstall.sh는 삭제 동작이므로 실제 실행하지 않음)

- [ ] **Step 5: Commit**

```bash
git add scripts/uninstall.sh scripts/cleanup_old_versions.sh
git commit -m "feat: uninstall HF_HOME 경로 갱신 + /tmp 잔재 제거 + cleanup 주석 보강"
```

---

## Task 14: README + 버전 범프

**Files:**
- Modify: `README.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`

- [ ] **Step 1: `README.md` 갱신**

1. 기능 목록의 `- macOS 지원`을 `- macOS · Windows 지원 (Claude Desktop 앱 Code 탭 / CLI)`로 변경.
2. "설치 전 준비물" 표를 다음으로 교체:

```markdown
| 필요한 것 | 비고 |
|---|---|
| Claude Code (CLI 또는 데스크톱 앱) | Windows는 **데스크톱 앱의 Code 탭 + Local 세션**에서 동작 (Chat 탭·Remote 세션 불가) |
| Windows: Git for Windows | 데스크톱 앱 Code 탭이 요구 — 설치 시 Git Bash 포함 |
| Python 3.9+ | macOS 기본 내장 / Windows: `winget install -e --id Python.Python.3.12` (Microsoft Store 버전은 비권장) |

`sounddevice`·`faster-whisper`·Whisper 모델(약 1.5GB)은 설치 후 첫 세션에서 플러그인이 자동으로 내려받습니다. SoX 등 외부 녹음 도구는 더 이상 필요 없습니다.
```

3. "## 동작 기본값" 위에 새 섹션 추가:

```markdown
## Windows에서 마이크가 안 잡힐 때

Windows는 데스크톱 앱 전체에 마이크 권한을 한 번에 부여합니다. 녹음이 실패하면:
**설정 > 개인정보 보호 및 보안 > 마이크** 에서
`마이크 액세스`, `앱이 마이크에 액세스하도록 허용`, `데스크톱 앱이 마이크에 액세스하도록 허용` 세 가지를 모두 켜세요.
```

- [ ] **Step 2: 버전 범프** — `1.4.19` → `1.5.0` (Windows 지원 = minor)

`.claude-plugin/plugin.json`의 `"version": "1.4.19"` → `"version": "1.5.0"`.
`.claude-plugin/marketplace.json`의 plugins[0] `"version": "1.4.19"` → `"version": "1.5.0"`.

> 메모리 규칙: plugin.json과 marketplace.json **둘 다** 올린다. 기존 필드는 절대 제거하지 않는다.

- [ ] **Step 3: JSON 유효성 + 버전 확인**

Run: `.venv/bin/python -c "import json; print(json.load(open('.claude-plugin/plugin.json'))['version'], json.load(open('.claude-plugin/marketplace.json'))['plugins'][0]['version'])"`
Expected: `1.5.0 1.5.0`

- [ ] **Step 4: Commit**

```bash
git add README.md .claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "docs: README 3환경 지원·마이크 권한 안내 + 버전 1.5.0"
```

---

## Task 15: 전체 테스트 + macOS 회귀 검증

**Files:** (없음 — 검증 전용)

- [ ] **Step 1: 전체 pytest 통과 확인**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: 20 passed (test_record.py 19 + test_transcribe_paths.py 1).

- [ ] **Step 2: macOS CLI end-to-end 회귀** — 실제 녹음→변환→저장

이 세션(macOS CLI)에서 임시 data 디렉토리로 전체 흐름 검증:
```bash
export MS_DATA_DIR=/tmp/ms-regress
WHISPER_MODEL=tiny bash scripts/setup.sh
bash scripts/start_recording.sh    # {"ok": true, "audio_path": ...}  (말하며 5초)
sleep 5
bash scripts/stop_recording.sh     # {"ok": true, ..., "duration_seconds": ~5}
AP="$(ls -t /tmp/ms-regress/state/recording_*.wav 2>/dev/null | head -1)"
[ -n "$AP" ] && WHISPER_MODEL=tiny bash scripts/transcribe.sh "$AP"
rm -rf /tmp/ms-regress; unset MS_DATA_DIR
```
Expected: start/stop 정상 JSON, transcribe가 transcript JSON. 마이크 권한 없으면 start가 한국어 안내 — 권한 허용 후 재검증.

- [ ] **Step 3: 결과 기록** — 통과 시 다음 단계로, 실패 시 systematic-debugging으로 원인 분석 후 해당 Task로 회귀 수정.

- [ ] **Step 4: Commit (수정이 있었을 때만)** — 검증 중 수정이 없으면 커밋 불필요.

---

## Task 16: Windows 실기 검증 (사용자 — 실제 Windows PC + Claude Desktop 앱)

**Files:** (없음 — 사용자 수동 검증)

스펙의 `mustVerifyOnRealWindows`에 대응한다. 사용자가 직접 수행하고 항목별 결과를 보고하면, 실패분에 한해 해당 Task로 돌아가 수정한다.

- [ ] **Step 1: 설치 + 탭/세션** — Desktop 앱 Code 탭 + Local 세션에서 플러그인 설치, `/meeting-simplifier:start|stop|summarize` 인식. Chat 탭/Remote 세션에서 비활성 확인.
- [ ] **Step 2: 셸 확인** — 세션에서 Bash 도구가 Git Bash로 동작하는지(`uname -a`가 MINGW* 반환) 확인. (Code 탭은 Git for Windows 필수이므로 Git Bash 기대.)
- [ ] **Step 3: 세션 hang 없음** — "녹음 시작" 후 세션이 멈추지 않고 즉시 응답(detach 정상, #43123 회피 확인).
- [ ] **Step 4: 녹음→회의록** — 실제 회의 녹음→중지→회의록 생성, `~/Documents/meetings`에 저장 확인.
- [ ] **Step 5: 마이크 권한 OFF/ON** — 데스크톱 앱 마이크 토글을 끈 상태에서 start가 한국어 안내를 반환하는지, 켜면 정상 녹음되는지.
- [ ] **Step 6: 워커 생명주기** — 녹음 중 앱/세션 종료 시 워커 동작(잔존 vs 종료) 관찰. 종료되면 "회의 중 세션 유지" 안내가 필요한지 판단(스펙 비목표).
- [ ] **Step 7: 결과 보고** — 항목별 OK/실패 정리해 보고. 실패분은 해당 Task로 회귀 수정.

---

## Self-Review 결과

- **Spec coverage:** 스펙의 9개 설계 결정 → Task 매핑 완료(녹음 단일화=T5/6/7, detach=T6/11, stop플래그=T7, /tmp제거=T8/13, venv/HF_HOME=T9, 마이크안내=T3/5, glob제거+폴백=T12, 셸 어댑터=T10, 위생=T1, uninstall=T13, README=T14, 검증=T15/16). 셸 전략은 bash 단일로 확정(Code 탭 Git Bash 보장) — PowerShell 어댑터 미작성.
- **Placeholder scan:** 코드 스텝은 전부 실제 코드 포함. `{회의록 내용}`·`{회의 제목}`·`<file_path>`·`<1단계 audio_path>`·`{2단계 transcript_file}`는 Claude가 런타임에 치환하는 의도된 플레이스홀더(원본 커맨드 규약 유지).
- **Type consistency:** `is_windows`/`data_dir`/`state_dir`/`state_paths`(키: pid/audio/stop/result/log/plugin_root)/`venv_python`/`friendly_device_error`/`report_error`/`wav_duration`/`pid_alive`/`run_worker`/`spawn_worker`/`is_recording`/`cmd_start`/`cmd_stop`/`force_kill`/`main` 시그니처가 정의/사용 태스크 전반에서 일치. 상수(SAMPLE_RATE/CHANNELS/SAMPLE_WIDTH/STOP_POLL_SECS/START_PROBE_SECS/STOP_WAIT_SECS)는 Task 2 정의분 재사용. `transcript_out_dir`(transcribe_server.py)는 T8에서 정의·사용.
- **검증 반영:** adversarial 리뷰 발견 전부 반영 — os.name→is_windows(critical), plugin_root cache-glob 폴백 복원(high), SessionEnd·stop.md 5단계 venv OS 분기(high), START_PROBE_SECS 테스트 patch·setup.sh docx best-effort·Task6 mkdir·uninstall /tmp 정리(nice-to-have). "shell 필드 부재" 지적은 공식 문서 재확인 결과 오탐이었으나, bash 단일 경로 단순화로 무관해짐.
