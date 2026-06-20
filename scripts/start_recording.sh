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
