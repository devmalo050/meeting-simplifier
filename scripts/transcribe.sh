#!/bin/bash
# scripts/transcribe.sh — 오디오 파일을 텍스트로 변환
# 사용법: bash transcribe.sh <audio_path>
# 출력: JSON {"transcript": "...", "language": "ko"}  또는  {"error": "..."}

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AUDIO_PATH="$1"

if [ -z "$AUDIO_PATH" ]; then
  echo '{"error": "audio_path가 필요합니다."}'
  exit 1
fi

if [ ! -f "$AUDIO_PATH" ]; then
  echo "{\"error\": \"파일이 없습니다: $AUDIO_PATH\"}"
  exit 1
fi

VENV_PYTHON="$PLUGIN_ROOT/.venv/bin/python"
if [ ! -f "$VENV_PYTHON" ]; then
  echo '{"error": "환경이 설치되지 않았습니다. 잠시 후 다시 시도하세요."}'
  exit 1
fi

WHISPER_MODEL="${WHISPER_MODEL:-medium}"
PID_DIR="/tmp/meeting-simplifier"
WARMUP_PID_FILE="$PID_DIR/warmup.pid"

# warmup 프로세스가 있으면 종료 (--oneshot으로 새로 실행)
if [ -f "$WARMUP_PID_FILE" ]; then
  WARMUP_PID=$(cat "$WARMUP_PID_FILE" 2>/dev/null)
  if [ -n "$WARMUP_PID" ]; then
    kill "$WARMUP_PID" 2>/dev/null
  fi
  rm -f "$WARMUP_PID_FILE"
fi

# 변환 실행 (stdout = JSON 결과)
WHISPER_MODEL="$WHISPER_MODEL" "$VENV_PYTHON" \
  "$PLUGIN_ROOT/scripts/transcribe_server.py" \
  --oneshot "$AUDIO_PATH"
