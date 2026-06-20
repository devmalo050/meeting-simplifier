---
description: >
  회의 녹음을 시작합니다.
  트리거: "회의 녹음 시작해줘", "녹음 시작", "녹음해줘", "회의 시작할게", "미팅 시작해",
  "회의 시작", "지금부터 회의 녹음", "회의 들어갈게",
  "record meeting", "start recording", "start meeting"
---

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
- `"ok": false` (status 키 없음 — env 통과 후 record 실패) → `error` 값을 사용자에게 그대로 전달하고 중단하세요(마이크 권한 거부·"이미 녹음 중" 등 안내 포함).
- `"status": "python_missing"` → "Python을 설치하겠습니다"라고 알린 뒤, **아래 `install_python.sh`만** 실행하고 그 결과 `message`를 사용자에게 그대로 전달하세요(특히 "세션을 새로 시작" 안내가 있으면 강조). 각 Bash 호출은 새 셸이라 변수가 보존되지 않으니 PLUGIN_DIR을 다시 유도합니다:
  ```bash
  DATA_DIR="${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}"
  PLUGIN_DIR="$(cat "$DATA_DIR/state/plugin_root" 2>/dev/null)"
  [ -z "$PLUGIN_DIR" ] && PLUGIN_DIR="$(ls -d ~/.claude/plugins/cache/*/meeting-simplifier/*/ 2>/dev/null | sort -V | tail -1)"
  [ -z "$PLUGIN_DIR" ] && PLUGIN_DIR=~/.claude/plugins/marketplaces/meeting-simplifier
  PLUGIN_DIR="${PLUGIN_DIR%/}"
  bash "$PLUGIN_DIR/scripts/install_python.sh"
  ```
- `"status": "venv_pending"` → 환경 준비를 백그라운드로 시작하고, 사용자에게 "환경 준비를 시작했습니다. 1~2분 후 다시 '녹음 시작'을 해주세요"라고만 안내하세요. 새 셸이라 DATA_DIR/PLUGIN_DIR을 다시 유도합니다:
  ```bash
  DATA_DIR="${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}"
  PLUGIN_DIR="$(cat "$DATA_DIR/state/plugin_root" 2>/dev/null)"
  [ -z "$PLUGIN_DIR" ] && PLUGIN_DIR="$(ls -d ~/.claude/plugins/cache/*/meeting-simplifier/*/ 2>/dev/null | sort -V | tail -1)"
  [ -z "$PLUGIN_DIR" ] && PLUGIN_DIR=~/.claude/plugins/marketplaces/meeting-simplifier
  PLUGIN_DIR="${PLUGIN_DIR%/}"
  MS_SETUP_MARKER="$DATA_DIR/.setup-complete" nohup bash "$PLUGIN_DIR/scripts/setup.sh" </dev/null >"$DATA_DIR/setup.log" 2>&1 &
  ```
- `"status": "installing"` → 직접 아무것도 실행하지 말고 `message`("…1~2분 후 다시 시도…")를 사용자에게 그대로 전달하세요.
- `"status": "deps_failed"` → `message`를 사용자에게 그대로 전달하고 중단하세요.
