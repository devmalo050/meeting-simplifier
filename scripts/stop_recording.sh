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
