# 회의록 저장 폴더 설정 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 일반인이 자연어로 회의록 저장 폴더를 변경/조회/리셋하고, 그 값을 `$MS_DATA_DIR/config.json`에 영구 저장한다.

**Architecture:** 신규 `config.py`가 설정 읽기/쓰기를 단일 책임으로 담당(import + CLI 양용). `save_meeting.py`는 `--output-dir` 미지정 시 `config`에서 출력 디렉토리를 읽는다(우선순위: 인자 > 설정 > 기본값). 신규 자연어 커맨드 `set-output-dir.md`가 위치를 해석해 `config.py` CLI를 호출한다.

**Tech Stack:** Python 3 표준 라이브러리(`json`, `os`, `argparse`, `pathlib`), pytest, Claude Code 플러그인 커맨드(.md).

## Global Constraints

- 외부 의존성 추가 금지 — Python 표준 라이브러리만 사용.
- 데이터 디렉토리 규칙은 `record.py`와 동일: `MS_DATA_DIR` 환경변수 우선, 없으면 `~/.claude/plugins/data/meeting-simplifier-meeting-simplifier`.
- 스크립트 결과는 JSON으로 stdout 출력(커맨드가 파싱) — 기존 관례.
- 기본 저장 경로 문자열은 정확히 `~/Documents/meetings` (확장 전 형태).
- config.json은 알 수 없는 키를 보존한다(전방 호환).
- 주석은 "왜"가 비자명할 때만(글로벌 규칙). 모든 파일 UTF-8, BOM 없음.
- 버전 bump 시 `.claude-plugin/plugin.json`과 `.claude-plugin/marketplace.json` 둘 다 갱신.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

### Task 1: config.py — 설정 읽기/쓰기 코어 + CLI

**Files:**
- Create: `scripts/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: 없음(독립).
- Produces:
  - `data_dir() -> pathlib.Path`
  - `config_path() -> pathlib.Path` (`<data_dir>/config.json`)
  - `load_config() -> dict` (파손/부재 시 `{}`)
  - `save_config(cfg: dict) -> None`
  - `get_output_dir() -> str | None`
  - `set_output_dir(path: str) -> str` (expanduser된 절대경로 반환, 디렉토리 생성 검증)
  - `unset_output_dir() -> None`
  - `effective_output_dir() -> str` (설정값 or `"~/Documents/meetings"`)
  - `DEFAULT_OUTPUT_DIR = "~/Documents/meetings"`
  - CLI: `--show` / `--set <PATH>` / `--reset` → JSON stdout

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_config.py`

```python
import sys
import json
import subprocess
import importlib
from pathlib import Path
import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def config_mod(tmp_path, monkeypatch):
    monkeypatch.setenv("MS_DATA_DIR", str(tmp_path))
    import config
    importlib.reload(config)
    return config


def test_get_output_dir_none_when_unset(config_mod):
    assert config_mod.get_output_dir() is None


def test_effective_falls_back_to_default(config_mod):
    assert config_mod.effective_output_dir() == "~/Documents/meetings"


def test_set_then_get_roundtrip(config_mod, tmp_path):
    target = tmp_path / "회의록"
    resolved = config_mod.set_output_dir(str(target))
    assert resolved == str(target)
    assert config_mod.get_output_dir() == str(target)
    assert target.is_dir()


def test_set_expands_user(config_mod, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    resolved = config_mod.set_output_dir("~/Desktop/x")
    assert resolved == str(tmp_path / "Desktop" / "x")


def test_unset_reverts_to_none(config_mod, tmp_path):
    config_mod.set_output_dir(str(tmp_path / "a"))
    config_mod.unset_output_dir()
    assert config_mod.get_output_dir() is None


def test_load_config_survives_corrupt_json(config_mod):
    p = config_mod.config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{ broken", encoding="utf-8")
    assert config_mod.get_output_dir() is None


def test_unknown_keys_preserved(config_mod, tmp_path):
    config_mod.save_config({"whisper_model": "small"})
    config_mod.set_output_dir(str(tmp_path / "b"))
    cfg = config_mod.load_config()
    assert cfg["whisper_model"] == "small"
    assert "output_dir" in cfg


def _run_cli(tmp_path, *args):
    import os
    env = dict(os.environ)
    env["MS_DATA_DIR"] = str(tmp_path)
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "config.py"), *args],
        capture_output=True, text=True, env=env,
    )
    return r, json.loads(r.stdout)


def test_cli_show_default(tmp_path):
    r, out = _run_cli(tmp_path, "--show")
    assert r.returncode == 0
    assert out["ok"] is True
    assert out["is_default"] is True
    assert out["output_dir"] == "~/Documents/meetings"


def test_cli_set_then_show(tmp_path):
    target = str(tmp_path / "out")
    _run_cli(tmp_path, "--set", target)
    r, out = _run_cli(tmp_path, "--show")
    assert out["ok"] is True
    assert out["is_default"] is False
    assert out["output_dir"] == target


def test_cli_reset(tmp_path):
    _run_cli(tmp_path, "--set", str(tmp_path / "out"))
    r, out = _run_cli(tmp_path, "--reset")
    assert out["ok"] is True
    assert out["is_default"] is True
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_config.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: 최소 구현** — `scripts/config.py`

```python
#!/usr/bin/env python3
# scripts/config.py
# 회의록 저장 폴더 등 플러그인 런타임 설정을 $MS_DATA_DIR/config.json에 보관.
# 사용법: python config.py --show | --set <PATH> | --reset  → JSON 결과 stdout
import sys
import os
import json
import argparse
from pathlib import Path

DEFAULT_OUTPUT_DIR = "~/Documents/meetings"


def data_dir():
    env = os.environ.get("MS_DATA_DIR")
    if env:
        return Path(env)
    return Path.home() / ".claude" / "plugins" / "data" / "meeting-simplifier-meeting-simplifier"


def config_path():
    return data_dir() / "config.json"


def load_config():
    try:
        with open(config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (FileNotFoundError, ValueError, OSError):
        pass
    return {}


def save_config(cfg):
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_output_dir():
    return load_config().get("output_dir")


def set_output_dir(path):
    resolved = str(Path(path).expanduser())
    Path(resolved).mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    cfg["output_dir"] = resolved
    save_config(cfg)
    return resolved


def unset_output_dir():
    cfg = load_config()
    cfg.pop("output_dir", None)
    save_config(cfg)


def effective_output_dir():
    return get_output_dir() or DEFAULT_OUTPUT_DIR


def main():
    parser = argparse.ArgumentParser()
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--show", action="store_true")
    g.add_argument("--set", metavar="PATH")
    g.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    try:
        if args.show:
            configured = get_output_dir()
            print(json.dumps({
                "ok": True,
                "output_dir": effective_output_dir(),
                "is_default": configured is None,
            }, ensure_ascii=False))
        elif args.set:
            resolved = set_output_dir(args.set)
            print(json.dumps({"ok": True, "output_dir": resolved}, ensure_ascii=False))
        else:
            unset_output_dir()
            print(json.dumps({
                "ok": True,
                "output_dir": DEFAULT_OUTPUT_DIR,
                "is_default": True,
            }, ensure_ascii=False))
    except OSError as e:
        print(json.dumps({"ok": False, "message": f"해당 경로를 사용할 수 없습니다: {e}"}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_config.py -q`
Expected: PASS (10 passed)

- [ ] **Step 5: 커밋**

```bash
git add scripts/config.py tests/test_config.py
git commit -m "$(cat <<'EOF'
feat: config.py — 회의록 저장 폴더 설정 읽기/쓰기 + CLI

$MS_DATA_DIR/config.json에 output_dir 저장. --show/--set/--reset CLI는
JSON 결과를 stdout으로 출력. 알 수 없는 키 보존, 파손 JSON 안전 폴백.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: save_meeting.py 우선순위 통합

**Files:**
- Modify: `scripts/save_meeting.py` (argparse 기본값 + 출력 디렉토리 결정)
- Test: `tests/test_save_meeting.py`

**Interfaces:**
- Consumes: Task 1의 `config.effective_output_dir()`.
- Produces: `resolve_output_dir(arg_output_dir: str | None) -> str`.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_save_meeting.py`

```python
import sys
import importlib
from pathlib import Path
import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def save_mod(tmp_path, monkeypatch):
    monkeypatch.setenv("MS_DATA_DIR", str(tmp_path))
    import config
    import save_meeting
    importlib.reload(config)
    importlib.reload(save_meeting)
    return save_meeting


def test_explicit_arg_wins(save_mod, tmp_path):
    import config
    config.set_output_dir(str(tmp_path / "cfg"))
    assert save_mod.resolve_output_dir("/explicit") == "/explicit"


def test_config_used_when_no_arg(save_mod, tmp_path):
    import config
    config.set_output_dir(str(tmp_path / "cfg"))
    assert save_mod.resolve_output_dir(None) == str(tmp_path / "cfg")


def test_default_when_nothing(save_mod):
    assert save_mod.resolve_output_dir(None) == "~/Documents/meetings"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/bin/python -m pytest tests/test_save_meeting.py -q`
Expected: FAIL — `AttributeError: module 'save_meeting' has no attribute 'resolve_output_dir'`

- [ ] **Step 3: 구현** — `scripts/save_meeting.py` 수정

상단 import 블록(`from pathlib import Path` 다음 줄)에 추가:

```python
import config
```

`main()`의 argparse에서 기존 줄:

```python
    parser.add_argument('--output-dir', default='~/Documents/meetings')
```

을 다음으로 교체:

```python
    parser.add_argument('--output-dir', default=None)
```

그리고 모듈 레벨에 함수 추가(`main()` 정의 바로 위):

```python
def resolve_output_dir(arg_output_dir):
    if arg_output_dir:
        return arg_output_dir
    return config.effective_output_dir()
```

`main()`에서 `save_meeting(...)` 호출의 `output_dir=args.output_dir`를 다음으로 교체:

```python
            output_dir=resolve_output_dir(args.output_dir),
```

- [ ] **Step 4: 테스트 통과 확인 (회귀 포함)**

Run: `.venv/bin/python -m pytest tests/test_save_meeting.py tests/test_config.py -q`
Expected: PASS (13 passed)

- [ ] **Step 5: 전체 회귀 테스트**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS (기존 30 + 신규 13 = 43 passed)

- [ ] **Step 6: 커밋**

```bash
git add scripts/save_meeting.py tests/test_save_meeting.py
git commit -m "$(cat <<'EOF'
feat: save_meeting.py가 config의 저장 폴더를 읽음

--output-dir 미지정 시 config.effective_output_dir() 사용
(우선순위: 명시 인자 > 설정 > 기본값 ~/Documents/meetings).
stop/summarize 커맨드는 --output-dir를 안 넘기므로 자동 적용.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: commands/set-output-dir.md — 자연어 스킬 커맨드

**Files:**
- Create: `commands/set-output-dir.md`

**Interfaces:**
- Consumes: Task 1의 `config.py` CLI(`--show`/`--set`/`--reset`).
- Produces: `meeting-simplifier:set-output-dir` 스킬(자동 노출).

- [ ] **Step 1: 커맨드 파일 작성** — `commands/set-output-dir.md`

기존 커맨드와 동일한 PLUGIN_DIR/DATA_DIR 유도 패턴을 쓴다. 전체 내용:

````markdown
---
description: >
  회의록이 저장되는 폴더를 변경/확인/초기화합니다.
  트리거: "회의록 저장 위치 바꿔줘", "회의록 저장 폴더 변경", "회의록 어디에 저장할지 바꿔줘",
  "회의록 저장 위치 알려줘", "회의록 지금 어디에 저장돼", "회의록 저장 폴더 원래대로",
  "change meeting save folder", "where are meetings saved", "reset meeting folder"
---

사용자의 의도를 다음 셋 중 하나로 판단해 진행하세요: **변경 / 조회 / 초기화**.

공통: 모든 작업은 아래 `config.py`만 호출해서 처리합니다. config.json을 직접 편집하지 마세요.

```bash
DATA_DIR="${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}"
PLUGIN_DIR="$(cat "$DATA_DIR/state/plugin_root" 2>/dev/null)"
[ -z "$PLUGIN_DIR" ] && PLUGIN_DIR="$(ls -d ~/.claude/plugins/cache/*/meeting-simplifier/*/ 2>/dev/null | sort -V | tail -1)"
[ -z "$PLUGIN_DIR" ] && PLUGIN_DIR=~/.claude/plugins/marketplaces/meeting-simplifier
PLUGIN_DIR="${PLUGIN_DIR%/}"
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) VENV_PY="$DATA_DIR/.venv/Scripts/python.exe";; *) VENV_PY="$DATA_DIR/.venv/bin/python";; esac
```

**조회** ("지금 어디에 저장돼?", "저장 위치 알려줘"):
```bash
"$VENV_PY" "$PLUGIN_DIR/scripts/config.py" --show
```
- `output_dir`를 사용자에게 안내합니다. `is_default`가 `true`면 "(기본값)"임을 덧붙입니다.

**초기화** ("원래대로", "초기화", "reset"):
```bash
"$VENV_PY" "$PLUGIN_DIR/scripts/config.py" --reset
```
- "회의록 저장 위치를 기본값(`~/Documents/meetings`)으로 되돌렸습니다"를 안내합니다.

**변경** ("바탕화면에 저장해줘", "저장 폴더 바꿔줘"):
1. 사용자가 말한 위치를 절대경로로 해석합니다. 일상 표현은 표준 폴더로 매핑하세요:
   - "바탕화면" → `~/Desktop`, "문서함"/"문서" → `~/Documents`, "다운로드" → `~/Downloads`
   - 하위 폴더명이 있으면 이어붙입니다(예: "바탕화면 회의록" → `~/Desktop/회의록`).
2. 위치가 모호하면 사용자에게 되묻습니다.
3. **저장 직전에 최종 경로를 사용자에게 보여주고 확인**받습니다(예: "`~/Desktop/회의록`에 저장하도록 설정할까요?").
4. 확인되면 실행합니다(경로는 따옴표로 감쌉니다):
   ```bash
   "$VENV_PY" "$PLUGIN_DIR/scripts/config.py" --set "<해석한 경로>"
   ```
   - `"ok": true` → "이제부터 회의록은 `{output_dir}`에 저장됩니다"를 안내합니다.
   - `"ok": false` → `message`를 사용자에게 그대로 전달합니다(직접 폴더를 만들거나 다른 명령을 시도하지 마세요).
````

- [ ] **Step 2: config.py CLI 수동 동작 확인 (커맨드가 부를 명령 직접 검증)**

Run:
```bash
MS_DATA_DIR=/tmp/ms_cmd_test .venv/bin/python scripts/config.py --show
MS_DATA_DIR=/tmp/ms_cmd_test .venv/bin/python scripts/config.py --set /tmp/ms_cmd_test/out
MS_DATA_DIR=/tmp/ms_cmd_test .venv/bin/python scripts/config.py --show
MS_DATA_DIR=/tmp/ms_cmd_test .venv/bin/python scripts/config.py --reset
rm -rf /tmp/ms_cmd_test
```
Expected: 순서대로 `is_default:true` → set된 경로 → `is_default:false` + 그 경로 → `is_default:true`. 모두 `ok:true`.

- [ ] **Step 3: 커밋**

```bash
git add commands/set-output-dir.md
git commit -m "$(cat <<'EOF'
feat: set-output-dir 커맨드 — 자연어로 저장 폴더 변경/조회/초기화

config.py CLI만 호출하도록 캡슐화(LLM 직접 편집 금지). 일상 표현을
표준 폴더로 매핑하고 저장 직전 경로 확인.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: 버전 bump + README 매뉴얼 (Windows/macOS 설치 + 저장 폴더 변경)

**Files:**
- Modify: `.claude-plugin/plugin.json` (version 1.5.1 → 1.6.0)
- Modify: `.claude-plugin/marketplace.json` (version 1.5.1 → 1.6.0)
- Modify: `README.md` (저장 폴더 변경 사용법 추가, Windows/macOS 설치 안내 점검)

**Interfaces:**
- Consumes: 없음.
- Produces: 없음(문서/메타).

- [ ] **Step 1: 버전 갱신** — 두 파일의 `"version": "1.5.1"`을 `"version": "1.6.0"`으로 변경. 다른 필드는 건드리지 않는다.

- [ ] **Step 2: 버전 일치 확인**

Run: `grep '"version"' .claude-plugin/plugin.json .claude-plugin/marketplace.json`
Expected: 둘 다 `1.6.0`.

- [ ] **Step 3: README 갱신** — `README.md`를 읽고 다음을 반영한다.

(a) "회의록 저장 위치 바꾸기" 섹션을 새로 추가한다(사용법 안내):

```markdown
## 회의록 저장 위치 바꾸기

회의록은 기본적으로 `~/Documents/meetings` 아래에 저장됩니다. 다른 폴더로 바꾸려면 그냥 말로 요청하세요.

- 변경: "회의록 저장 위치 바꿔줘" 또는 "회의록 바탕화면에 저장해줘"
- 확인: "회의록 지금 어디에 저장돼?"
- 초기화: "회의록 저장 위치 원래대로 돌려줘"

설정한 폴더는 이후 모든 회의록에 계속 적용됩니다(어느 위치에서 녹음하든 동일).
```

(b) Windows/macOS 설치 안내(설치·첫 실행 섹션)를 점검한다. 기존 설치 단계가 정확한지 확인하고, 회의록 저장 위치를 바꿀 수 있다는 한 줄을 첫 실행 안내 근처에 추가한다. 설치 절차 자체가 이번 변경으로 달라지지 않았다면 새 섹션 링크만 추가하고 과한 수정은 하지 않는다(변경 범위 최소화).

- [ ] **Step 4: 커밋**

```bash
git add .claude-plugin/plugin.json .claude-plugin/marketplace.json README.md
git commit -m "$(cat <<'EOF'
docs: README 저장 폴더 변경 안내 + 버전 1.6.0

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## 완료 기준

- `.venv/bin/python -m pytest tests/ -q` → 43 passed (기존 30 + 신규 13).
- `bash -n scripts/config.py` 불필요(파이썬). `python -c "import ast; ast.parse(open('scripts/config.py').read())"`로 문법 확인 가능.
- `meeting-simplifier:set-output-dir` 스킬이 변경/조회/초기화 3분기로 동작.
- `plugin.json`·`marketplace.json` 모두 1.6.0.
- README에 저장 폴더 변경 사용법 존재.
