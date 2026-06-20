# Windows Python 자동 설치 + 결정론적 온보딩 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 완전 새 Windows PC(Python 미설치)에서 플러그인 첫 사용 시, Claude의 즉흥적 winget trial-and-error 대신 결정론적·가이드된 설치 흐름으로 Python·의존성이 준비되게 한다.

**Architecture:** 환경 상태를 공통 셸(`lib_env.sh`)이 열거형으로 판단하고, 어댑터(`start_recording.sh`/`transcribe.sh`)가 `status`+`message` JSON으로 보고한다. Python 설치는 전용 결정론 스크립트(`install_python.sh`)가 winget으로 수행하고, 커맨드 `.md`는 `status`별로 "정해진 스크립트만 호출"하도록 Claude를 묶는다.

**Tech Stack:** bash(macOS sh / Windows Git Bash, uname 분기), winget(Python.Python.3.12 classic), 기존 Python venv(faster-whisper/sounddevice), pytest(subprocess로 셸 테스트).

**참조 스펙:** `docs/superpowers/specs/2026-06-20-onboarding-python-install-design.md`

## Global Constraints

- 한국어: 응답·주석·커밋 메시지·사용자 노출 메시지 모두 한국어.
- 주석: 기본 무주석, "왜"가 비자명할 때만. docstring은 한 줄.
- 인코딩: 모든 파일 UTF-8(BOM 없음).
- 버전: 수정 시 `.claude-plugin/plugin.json`과 `marketplace.json` **둘 다** 올린다. 기존 필드 제거 금지.
- 셸: bash 단일. OS 분기는 `case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) ... ;; *) ... ;; esac`.
- Python 설치 패키지: classic `Python.Python.3.12`(pymanager 미사용).
- 테스트 실행: `.venv/bin/python -m pytest`.
- 상태 디렉토리: `DATA_DIR=${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}`, `STATE_DIR=$DATA_DIR/state`.
- venv python: POSIX `$DATA_DIR/.venv/bin/python`, Windows `$DATA_DIR/.venv/Scripts/python.exe`.

## 두 종류의 status (혼동 방지)

- **환경 status** (`lib_env.sh ms_env_status`가 계산, 어댑터가 반환): `ready` | `installing` | `deps_failed` | `venv_pending` | `python_missing`. → 커맨드 1차 분기.
- **설치 결과 status** (`install_python.sh`가 반환): `python_present` | `python_installed_restart_needed` | `python_install_failed` | `python_missing_no_winget` | `python_missing`. → 커맨드가 `python_missing`일 때 install_python.sh를 호출하고 그 `message`를 사용자에게 전달.

---

## 파일 구조

**신규**
- `scripts/lib_env.sh` — 환경 상태 판단 공통 함수(`ms_data_dir`/`ms_venv_python`/`ms_python_present`/`ms_env_status`/`ms_env_message`). source용 + `status` 인자 CLI.
- `scripts/install_python.sh` — Python 탐지/설치(Windows winget) 단일 책임, JSON status 반환.
- `tests/test_env_shell.py` — lib_env.sh / install_python.sh 동작 테스트(pytest subprocess).

**수정**
- `scripts/setup.sh` — Python 없을 때 `setup_status=python_missing` 기록(echo+exit 대신), 단계별 `setup_status` 전이, 종료 시 `ready`.
- `scripts/start_recording.sh` — lib_env source + 환경 status JSON 반환.
- `scripts/transcribe.sh` — lib_env source + 환경 status JSON 반환.
- `commands/start.md`/`stop.md`/`summarize.md` — status별 결정론 분기 + install_python.sh 지시.
- `README.md` — Windows 첫 실행 흐름(Python 자동 설치 → UAC 예 → 세션 재시작) 안내.
- `.claude-plugin/plugin.json`/`marketplace.json` — 1.5.0 → 1.5.1.

---

## Task 1: `lib_env.sh` — 환경 상태 판단 공통 셸 (TDD)

**Files:**
- Create: `scripts/lib_env.sh`
- Test: `tests/test_env_shell.py`

**Interfaces:**
- Produces: `ms_env_status`(stdout: `ready`|`installing`|`deps_failed`|`venv_pending`|`python_missing`), `ms_venv_python`(stdout: venv python 절대경로), `ms_env_message <status>`(stdout: 한국어 안내), `ms_python_present`(exit 0/1). CLI: `bash scripts/lib_env.sh status` → status 한 줄.

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_env_shell.py`

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_env_shell.py -v`
Expected: FAIL (lib_env.sh 없음 — bash가 파일 못 찾아 빈 출력/에러).

- [ ] **Step 3: `scripts/lib_env.sh` 구현**

```bash
#!/usr/bin/env bash
# scripts/lib_env.sh — 환경 상태 판단 공통 함수 (source 하거나 'status' 인자로 직접 실행)

ms_data_dir() {
  printf '%s' "${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}"
}

ms_venv_python() {
  local d; d="$(ms_data_dir)"
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) printf '%s' "$d/.venv/Scripts/python.exe" ;;
    *) printf '%s' "$d/.venv/bin/python" ;;
  esac
}

ms_python_present() {
  local c
  for c in py python python3; do command -v "$c" &>/dev/null && return 0; done
  return 1
}

ms_env_status() {
  local d vp status_file raw
  d="$(ms_data_dir)"
  vp="$(ms_venv_python)"
  if [ -f "$vp" ] && "$vp" -c "import faster_whisper, sounddevice" 2>/dev/null; then
    printf 'ready'; return
  fi
  status_file="$d/state/setup_status"
  raw=""; [ -f "$status_file" ] && raw="$(cat "$status_file" 2>/dev/null)"
  case "$raw" in
    failed:*) printf 'deps_failed'; return ;;
    installing_deps|downloading_model) printf 'installing'; return ;;
  esac
  if ms_python_present; then printf 'venv_pending'; else printf 'python_missing'; fi
}

ms_env_message() {
  case "$1" in
    python_missing) printf 'Python이 설치되어 있지 않습니다.' ;;
    venv_pending) printf '환경 준비가 필요합니다. 설치를 시작합니다.' ;;
    installing) printf '환경 설치가 진행 중입니다. 1~2분 후 다시 시도하세요.' ;;
    deps_failed) printf '환경 설치에 실패했습니다. 잠시 후 다시 시도하거나 세션을 새로 시작하세요.' ;;
    *) printf '환경이 준비되지 않았습니다.' ;;
  esac
}

if [ "${BASH_SOURCE[0]}" = "${0}" ] && [ "${1:-}" = "status" ]; then
  ms_env_status; echo
fi
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_env_shell.py -v`
Expected: 4 passed (venv_pending/installing/deps_failed/ready).

- [ ] **Step 5: Commit**

```bash
git add scripts/lib_env.sh tests/test_env_shell.py
git commit -m "feat: lib_env.sh — 환경 상태 열거형 판단 공통 셸(ready/installing/deps_failed/venv_pending/python_missing)"
```

---

## Task 2: `install_python.sh` — Python 자동 설치 (TDD)

**Files:**
- Create: `scripts/install_python.sh`
- Test: `tests/test_env_shell.py` (추가)

**Interfaces:**
- Produces: `install_python.sh` 실행 → stdout JSON `{"ok":bool,"status":"python_present|python_installed_restart_needed|python_install_failed|python_missing_no_winget|python_missing","message":"..."}`. Python 존재 시 즉시 `python_present`.

- [ ] **Step 1: 실패 테스트 추가** — `tests/test_env_shell.py` 끝에

```python
import json


def test_install_python_present_when_python_exists():
    r = subprocess.run(
        ["bash", str(SCRIPTS / "install_python.sh")],
        capture_output=True, text=True,
    )
    data = json.loads(r.stdout)
    assert data["ok"] is True
    assert data["status"] == "python_present"
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_env_shell.py -k install_python -v`
Expected: FAIL (install_python.sh 없음 → JSONDecodeError).

- [ ] **Step 3: `scripts/install_python.sh` 구현**

```bash
#!/usr/bin/env bash
# scripts/install_python.sh — Python 탐지 후 없으면 설치(Windows winget). JSON status 출력.

for cmd in py python python3; do
  if command -v "$cmd" &>/dev/null; then
    printf '%s\n' '{"ok": true, "status": "python_present", "message": "Python이 이미 설치되어 있습니다."}'
    exit 0
  fi
done

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    if command -v winget &>/dev/null; then
      if MSYS_NO_PATHCONV=1 winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements; then
        printf '%s\n' '{"ok": true, "status": "python_installed_restart_needed", "message": "Python을 설치했습니다. (UAC 권한 창이 떴다면 \"예\"를 누르셨을 겁니다.) 적용을 위해 Claude 세션을 완전히 새로 시작한 뒤 다시 \"회의 녹음 시작\"을 해주세요."}'
        exit 0
      else
        printf '%s\n' '{"ok": false, "status": "python_install_failed", "message": "Python 자동 설치에 실패했습니다. https://www.python.org/downloads/windows/ 에서 Python을 설치(설치 화면에서 Add python.exe to PATH 체크)한 뒤 Claude 세션을 새로 시작해주세요."}'
        exit 1
      fi
    else
      printf '%s\n' '{"ok": false, "status": "python_missing_no_winget", "message": "Python과 winget이 모두 없습니다. https://www.python.org/downloads/windows/ 에서 Python을 설치(Add python.exe to PATH 체크)한 뒤 Claude 세션을 새로 시작해주세요."}'
      exit 1
    fi
    ;;
  Darwin)
    printf '%s\n' '{"ok": false, "status": "python_missing", "message": "Python이 없습니다. brew install python 으로 설치한 뒤 다시 시도하세요."}'
    exit 1
    ;;
  *)
    printf '%s\n' '{"ok": false, "status": "python_missing", "message": "Python이 없습니다. 배포판 패키지(예: apt install python3)로 설치한 뒤 다시 시도하세요."}'
    exit 1
    ;;
esac
```

- [ ] **Step 4: 통과 확인 + 문법**

Run: `bash -n scripts/install_python.sh && .venv/bin/python -m pytest tests/test_env_shell.py -k install_python -v`
Expected: 문법 정상, 1 passed (macOS에 python3 존재 → python_present).

- [ ] **Step 5: Commit**

```bash
git add scripts/install_python.sh tests/test_env_shell.py
git commit -m "feat: install_python.sh — Python 탐지/자동설치(Windows winget classic 3.12) JSON status"
```

---

## Task 3: `setup.sh` — setup_status 전이 + Python 부재 기록

**Files:**
- Modify: `scripts/setup.sh`

setup.sh가 단계별로 `STATE_DIR/setup_status`를 갱신하고, Python이 없으면 echo+exit 대신 `python_missing`을 기록한다. 어댑터(`ms_env_status`)가 이 파일을 읽어 `installing`/`deps_failed`를 판단한다.

- [ ] **Step 1: `setup.sh` 상단에 STATE_DIR + 헬퍼 추가** — `mkdir -p "$DATA_DIR"`(6행) 바로 뒤에 삽입

```bash
STATE_DIR="$DATA_DIR/state"
mkdir -p "$STATE_DIR"
set_status() { printf '%s' "$1" > "$STATE_DIR/setup_status"; }
```

- [ ] **Step 2: Python 부재 처리 교체** — 기존 27-30행

```bash
if [ -z "$PYTHON_CMD" ]; then
  echo "⚠️  Python이 없습니다. Windows: winget install -e --id Python.Python.3.12 / macOS: brew install python"
  exit 1
fi
```

을 다음으로 교체:

```bash
if [ -z "$PYTHON_CMD" ]; then
  set_status "python_missing"
  echo "⚠️  Python이 없습니다. '회의 녹음 시작' 시 자동 설치 안내가 진행됩니다."
  exit 1
fi
```

- [ ] **Step 3: 의존성 설치 직전에 status 기록** — 기존 핵심 의존성 설치 `if ! "$VENV_PYTHON" -c "import faster_whisper, sounddevice, psutil, numpy" ...` 블록 **바로 위**에 추가

```bash
set_status "installing_deps"
```

- [ ] **Step 4: 모델 다운로드 직전에 status 기록** — 기존 `if [ ! -d "$MODEL_CACHE" ]; then` **바로 위**에 추가

```bash
set_status "downloading_model"
```

- [ ] **Step 5: 종료 시 ready 기록** — 파일 맨 끝(마커 기록 블록 뒤)에 추가

```bash
set_status "ready"
```

- [ ] **Step 6: 문법 + 전이 검증**

Run:
```bash
bash -n scripts/setup.sh
MS_DATA_DIR=/tmp/ms-st MS_SETUP_MARKER=/tmp/ms-st/.done WHISPER_MODEL=tiny bash scripts/setup.sh >/dev/null 2>&1
cat /tmp/ms-st/state/setup_status; echo
rm -rf /tmp/ms-st
```
Expected: 문법 정상, 최종 `setup_status` = `ready`.

- [ ] **Step 7: Commit**

```bash
git add scripts/setup.sh
git commit -m "feat: setup.sh 단계별 setup_status 전이(installing_deps/downloading_model/ready) + Python 부재 시 python_missing 기록"
```

---

## Task 4: `start_recording.sh` / `transcribe.sh` — 환경 status 보고

**Files:**
- Modify: `scripts/start_recording.sh`, `scripts/transcribe.sh`

venv 미준비 시 단일 error 대신 `ms_env_status` 결과를 `status`+`message` JSON으로 반환한다.

**Interfaces:**
- Consumes: Task 1의 `ms_env_status`/`ms_env_message`/`ms_venv_python` (source).

- [ ] **Step 1: `start_recording.sh` 교체**

```bash
#!/usr/bin/env bash
# scripts/start_recording.sh — record.py start 어댑터
PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$PLUGIN_ROOT/scripts/lib_env.sh"

ST="$(ms_env_status)"
if [ "$ST" != "ready" ]; then
  printf '{"ok": false, "status": "%s", "message": "%s"}\n' "$ST" "$(ms_env_message "$ST")"
  exit 0
fi
"$(ms_venv_python)" "$PLUGIN_ROOT/scripts/record.py" start </dev/null
```

- [ ] **Step 2: `transcribe.sh` 교체**

```bash
#!/usr/bin/env bash
# scripts/transcribe.sh — 오디오 → 텍스트 (record.py와 동일 venv 사용)
PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$PLUGIN_ROOT/scripts/lib_env.sh"
AUDIO_PATH="$1"
DATA_DIR="$(ms_data_dir)"

if [ -z "$AUDIO_PATH" ]; then echo '{"error": "audio_path가 필요합니다."}'; exit 1; fi
if [ ! -f "$AUDIO_PATH" ]; then echo "{\"error\": \"파일이 없습니다: $AUDIO_PATH\"}"; exit 1; fi

ST="$(ms_env_status)"
if [ "$ST" != "ready" ]; then
  printf '{"ok": false, "status": "%s", "message": "%s"}\n' "$ST" "$(ms_env_message "$ST")"
  exit 0
fi

export HF_HOME="$DATA_DIR/hf"
WHISPER_MODEL="${WHISPER_MODEL:-medium}" HF_HOME="$HF_HOME" "$(ms_venv_python)" \
  "$PLUGIN_ROOT/scripts/transcribe_server.py" --oneshot "$AUDIO_PATH"
```

- [ ] **Step 3: 문법 + 동작 확인**

Run:
```bash
bash -n scripts/start_recording.sh scripts/transcribe.sh
MS_DATA_DIR=/tmp/ms-ad bash scripts/start_recording.sh
rm -rf /tmp/ms-ad
```
Expected: 문법 정상. venv 없는 임시 디렉토리라 `{"ok": false, "status": "venv_pending", "message": "환경 준비가 필요합니다. 설치를 시작합니다."}` 반환(시스템 python 존재 시).

- [ ] **Step 4: 전체 테스트 회귀**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 모두 passed(record.py 25 + env_shell 5).

- [ ] **Step 5: Commit**

```bash
git add scripts/start_recording.sh scripts/transcribe.sh
git commit -m "feat: 녹음/변환 어댑터가 환경 status+message JSON 보고(lib_env source)"
```

---

## Task 5: `commands/*.md` — status별 결정론 분기

**Files:**
- Modify: `commands/start.md`, `commands/stop.md`, `commands/summarize.md`

어댑터가 반환한 `status`별로 Claude에게 고정 행동을 지시한다. 핵심: Python 설치는 `install_python.sh`로만, 임의 winget/pip/python 명령 금지.

공통 PLUGIN_DIR 해석(모든 블록에서 사용, 기존과 동일):
```bash
DATA_DIR="${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}"
PLUGIN_DIR="$(cat "$DATA_DIR/state/plugin_root" 2>/dev/null)"
[ -z "$PLUGIN_DIR" ] && PLUGIN_DIR="$(ls -d ~/.claude/plugins/cache/*/meeting-simplifier/*/ 2>/dev/null | sort -V | tail -1)"
[ -z "$PLUGIN_DIR" ] && PLUGIN_DIR=~/.claude/plugins/marketplaces/meeting-simplifier
PLUGIN_DIR="${PLUGIN_DIR%/}"
```

- [ ] **Step 1: `commands/start.md` 본문 교체** (frontmatter 유지)

frontmatter 아래를 다음으로 교체:

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

결과 JSON으로 분기합니다. **임의의 winget/pip/python 설치 명령을 직접 만들지 말고, 아래 정해진 행동만 하세요.**

- `"ok": true` → "녹음을 시작했습니다. 회의가 끝나면 '녹음 끝' 또는 '회의록 만들어줘' 라고 말씀해주세요."
- `"status": "python_missing"` → "Python을 설치하겠습니다"라고 알린 뒤, **아래 `install_python.sh`만** 실행하고 그 결과 `message`를 사용자에게 그대로 전달하세요(특히 "세션을 새로 시작" 안내가 있으면 강조):
  ```bash
  bash "$PLUGIN_DIR/scripts/install_python.sh"
  ```
- `"status": "venv_pending"` → 환경 준비를 백그라운드로 시작하고, 사용자에게 "환경 준비를 시작했습니다. 1~2분 후 다시 '녹음 시작'을 해주세요"라고만 안내하세요:
  ```bash
  MS_SETUP_MARKER="$DATA_DIR/.setup-complete" nohup bash "$PLUGIN_DIR/scripts/setup.sh" </dev/null >"$DATA_DIR/setup.log" 2>&1 &
  ```
- `"status": "installing"` → 직접 아무것도 실행하지 말고 `message`("…1~2분 후 다시 시도…")를 사용자에게 그대로 전달하세요.
- `"status": "deps_failed"` → `message`를 사용자에게 그대로 전달하고 중단하세요.
````

- [ ] **Step 2: `commands/stop.md` 2단계(변환) 분기 추가**

2단계 `transcribe.sh` 호출 블록 뒤의 결과 처리에 다음을 반영(기존 `error` 키 처리에 더해): 변환 결과에 `"status"`가 있고 `"ok": false`면, `status`가 `installing`/`venv_pending`/`python_missing`/`deps_failed` 중 무엇이든 **직접 설치 명령을 만들지 말고** `message`를 사용자에게 그대로 전달하고 중단한다. `python_missing`이면 start.md와 동일하게 `install_python.sh`만 실행하도록 안내한다. (1·3~6단계는 변경하지 않는다.)

- [ ] **Step 3: `commands/summarize.md` 동일 분기 추가**

오디오 변환(`transcribe.sh`) 결과에 `"status"`+`"ok": false`가 있으면 stop.md Step 2와 동일하게 처리한다(message 전달, python_missing이면 install_python.sh만). 텍스트 파일 경로는 영향 없음.

- [ ] **Step 4: 잔재 확인**

Run: `grep -c "install_python.sh" commands/start.md; grep -c "임의의 winget" commands/start.md`
Expected: 각 1 이상(분기·금지 지시 포함).

- [ ] **Step 5: Commit**

```bash
git add commands/start.md commands/stop.md commands/summarize.md
git commit -m "feat: 커맨드 status별 결정론 분기 — python_missing은 install_python.sh만, winget 직접 실행 금지"
```

---

## Task 6: README + 버전 범프

**Files:**
- Modify: `README.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`

- [ ] **Step 1: `README.md`의 "Windows에서 마이크가 안 잡힐 때" 섹션 앞에 새 섹션 추가**

```markdown
## Windows 첫 실행 (Python 자동 설치)

Python이 없는 새 PC라면, 처음 **"회의 녹음 시작"** 할 때 플러그인이 Python 설치를 안내합니다:
1. Python을 자동 설치합니다. **권한(UAC) 창이 뜨면 "예"**를 눌러주세요.
2. 설치 후 **Claude 세션을 완전히 새로 시작**하세요(설치된 Python을 인식하기 위함 — Windows 특성).
3. 다시 "회의 녹음 시작"을 하면 나머지(음성 인식 의존성·모델)가 자동으로 준비됩니다.

winget이 없는 환경이면 [python.org](https://www.python.org/downloads/windows/)에서 Python을 설치(설치 화면에서 "Add python.exe to PATH" 체크)한 뒤 세션을 새로 시작하세요.
```

- [ ] **Step 2: 버전 범프** — `1.5.0` → `1.5.1`

`.claude-plugin/plugin.json`의 `"version": "1.5.0"` → `"version": "1.5.1"`.
`.claude-plugin/marketplace.json`의 plugins[0] `"version": "1.5.0"` → `"version": "1.5.1"`.

- [ ] **Step 3: JSON + 버전 확인**

Run: `.venv/bin/python -c "import json; print(json.load(open('.claude-plugin/plugin.json'))['version'], json.load(open('.claude-plugin/marketplace.json'))['plugins'][0]['version'])"`
Expected: `1.5.1 1.5.1`

- [ ] **Step 4: Commit**

```bash
git add README.md .claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "docs: README Windows 첫 실행(Python 자동설치) 안내 + 버전 1.5.1"
```

---

## Task 7: 전체 테스트 + macOS 회귀 검증

**Files:** (없음 — 검증 전용)

- [ ] **Step 1: 전체 pytest**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 모두 passed (record.py 25 + env_shell 5 = 30).

- [ ] **Step 2: macOS 회귀 — 환경 status가 ready로 정상 녹음**

Run:
```bash
export MS_DATA_DIR=/tmp/ms-reg; rm -rf /tmp/ms-reg; mkdir -p /tmp/ms-reg/state
ln -s "$(pwd)/.venv" /tmp/ms-reg/.venv
PLUGIN_DIR="$(pwd)"
bash "$PLUGIN_DIR/scripts/start_recording.sh"   # ready → record.py start
sleep 2
.venv/bin/python "$PLUGIN_DIR/scripts/record.py" stop
rm -rf /tmp/ms-reg; unset MS_DATA_DIR
```
Expected: start가 `{"ok": true, "audio_path": ...}`(ready 경로), stop이 `{"ok": true, ...}`. 마이크 권한 없으면 start가 마이크 안내 — 정상.

- [ ] **Step 3: 결과 기록** — 통과 시 다음, 실패 시 systematic-debugging으로 원인 분석 후 해당 Task로.

- [ ] **Step 4: Commit (수정 있었을 때만)**

---

## Task 8: Windows 실기 검증 (사용자 — 새 Windows PC + Claude Desktop 앱)

**Files:** (없음 — 사용자 수동 검증)

- [ ] **Step 1: Python 없는 새 PC에서** 플러그인 설치 → "회의 녹음 시작" → `python_missing` 안내 + `install_python.sh` 자동 호출 확인.
- [ ] **Step 2: winget 설치 진행** — UAC 창 "예" → "세션 새로 시작" 안내 노출 확인.
- [ ] **Step 3: 세션 재시작 후** "회의 녹음 시작" → 의존성·모델 자동 준비(installing 안내) → 준비 완료 후 녹음 성공.
- [ ] **Step 4: winget 없는 환경**(가능하면)에서 `python_missing_no_winget` 단일 안내 노출 확인.
- [ ] **Step 5: Claude가 임의 winget을 직접 치지 않고** 정해진 스크립트만 호출하는지 관찰(trial-and-error 소멸 확인).
- [ ] **Step 6: 결과 보고** — 실패 항목은 해당 Task로 회귀 수정.

---

## Self-Review 결과

- **Spec coverage:** 스펙 결정 → Task 매핑: install_python.sh=T2, 상태 열거형 보고=T1(셸로 구현, 스펙의 record.py env_status를 Python 부재 판단 가능한 lib_env.sh로 조정 — 의도 동일), setup_status 전이=T3, 어댑터 status=T4, 커맨드 분기=T5, README+버전=T6, 검증=T7/T8. 부트스트랩(훅 fire-and-forget 유지 + 가시 시점 설치)은 기존 hooks.json 유지 + start.md의 venv_pending/python_missing 분기로 충족(훅 변경 불필요).
- **Placeholder scan:** 코드 스텝 전부 실제 코드. 커맨드 `.md`의 `{회의록 내용}` 등은 기존 런타임 플레이스홀더(유지).
- **Type consistency:** 환경 status 5값(ready/installing/deps_failed/venv_pending/python_missing)이 lib_env.sh 정의 → 어댑터 반환 → 커맨드 분기에서 일치. 설치 결과 status 5값이 install_python.sh 정의 → 커맨드 message 전달에서 일치. `ms_env_status`/`ms_venv_python`/`ms_env_message`/`ms_data_dir`/`ms_python_present` 시그니처가 Task 1 정의분과 Task 4 사용분에서 일치. `setup_status` 파일 값(installing_deps/downloading_model/ready/failed:*/python_missing)이 setup.sh(T3) 기록과 lib_env.sh(T1) 해석에서 일치.
