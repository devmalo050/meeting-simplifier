#!/usr/bin/env bash
# scripts/stop_recording.sh — record.py stop 어댑터
PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=scripts/lib_env.sh
. "$PLUGIN_ROOT/scripts/lib_env.sh"
VENV_PYTHON="$(ms_venv_python)"
if [ ! -f "$VENV_PYTHON" ]; then
  echo '{"ok": false, "error": "환경이 아직 준비되지 않았습니다."}'; exit 0
fi
"$VENV_PYTHON" "$PLUGIN_ROOT/scripts/record.py" stop </dev/null
