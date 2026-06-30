#!/usr/bin/env bash
# scripts/transcribe.sh — 오디오 → 텍스트 (record.py와 동일 venv 사용)
PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$PLUGIN_ROOT/scripts/lib_env.sh"
AUDIO_PATH="$1"
DATA_DIR="$(ms_data_dir)"

if [ -z "$AUDIO_PATH" ]; then echo '{"error": "audio_path가 필요합니다."}'; exit 1; fi
if [ ! -f "$AUDIO_PATH" ]; then echo '{"error": "파일이 없습니다."}'; exit 1; fi

ST="$(ms_env_status)"
if [ "$ST" != "ready" ]; then
  printf '{"ok": false, "status": "%s", "message": "%s"}\n' "$ST" "$(ms_env_message "$ST")"
  exit 0
fi

export HF_HOME="$DATA_DIR/hf"
WHISPER_MODEL="${WHISPER_MODEL:-medium}" "$(ms_venv_python)" \
  "$PLUGIN_ROOT/scripts/transcribe_server.py" --oneshot "$AUDIO_PATH"
