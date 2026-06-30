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
- `"ok": true` → "회의록 저장 위치를 기본값(`~/Documents/meetings`)으로 되돌렸습니다"를 안내합니다.
- `"ok": false` → `message`를 사용자에게 그대로 전달합니다(직접 폴더를 만들거나 다른 명령을 시도하지 마세요).

**변경** ("바탕화면에 저장해줘", "저장 폴더 바꿔줘"):
1. 사용자가 말한 위치를 절대경로로 해석합니다. 일상 표현은 표준 폴더로 매핑하세요:
   - "바탕화면" → `~/Desktop`, "문서함"/"문서" → `~/Documents`, "다운로드" → `~/Downloads`
   - 하위 폴더명이 있으면 이어붙입니다(예: "바탕화면 회의록" → `~/Desktop/회의록`).
2. 위치가 모호하면 사용자에게 되묻습니다.
3. **저장 직전에 최종 경로를 사용자에게 보여주고 확인**받습니다(예: "`~/Desktop/회의록`에 저장하도록 설정할까요?").
4. 확인되면 실행합니다(경로는 작은따옴표 변수에 담아 전달하며, 경로에 작은따옴표(`'`)가 들어 있으면 사용자에게 다시 확인합니다):
   ```bash
   MS_OUTDIR='<해석한 경로>'
   "$VENV_PY" "$PLUGIN_DIR/scripts/config.py" --set "$MS_OUTDIR"
   ```
   - `"ok": true` → "이제부터 회의록은 `{output_dir}`에 저장됩니다"를 안내합니다.
   - `"ok": false` → `message`를 사용자에게 그대로 전달합니다(직접 폴더를 만들거나 다른 명령을 시도하지 마세요).
