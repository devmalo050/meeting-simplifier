#!/bin/bash
# scripts/start_recording.sh — 마이크 녹음 시작
# 출력: JSON {"ok": true, "audio_path": "..."}  또는  {"ok": false, "error": "..."}

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PID_DIR="/tmp/meeting-simplifier"
PID_FILE="$PID_DIR/rec.pid"
AUDIO_FILE="$PID_DIR/audio_path"

mkdir -p "$PID_DIR"

# 이미 녹음 중이면 에러
if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE" 2>/dev/null)
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo '{"ok": false, "error": "이미 녹음 중입니다."}'
    exit 0
  fi
  rm -f "$PID_FILE" "$AUDIO_FILE"
fi

# 출력 파일 경로
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
WAV_PATH="$PID_DIR/recording_${TIMESTAMP}.wav"

# rec 존재 확인
if ! command -v rec &>/dev/null; then
  echo '{"ok": false, "error": "rec 명령어가 없습니다. brew install sox 를 실행하세요."}'
  exit 0
fi

# 백그라운드 녹음 시작
rec -q -r 16000 -c 1 -b 16 -e signed-integer "$WAV_PATH" &
REC_PID=$!

# 프로세스 확인
sleep 0.3
if ! kill -0 "$REC_PID" 2>/dev/null; then
  echo '{"ok": false, "error": "녹음 시작에 실패했습니다."}'
  exit 0
fi

echo "$REC_PID" > "$PID_FILE"
echo "$WAV_PATH" > "$AUDIO_FILE"

# warmup: transcribe_server.py를 백그라운드에서 미리 로딩 (모델 캐시)
VENV_PYTHON="$PLUGIN_ROOT/.venv/bin/python"
WHISPER_MODEL="${WHISPER_MODEL:-medium}"
WARMUP_PID_FILE="$PID_DIR/warmup.pid"

if [ -f "$VENV_PYTHON" ] && [ ! -f "$WARMUP_PID_FILE" ]; then
  (
    WHISPER_MODEL="$WHISPER_MODEL" "$VENV_PYTHON" "$PLUGIN_ROOT/scripts/transcribe_server.py" \
      2>"$PID_DIR/warmup.log" &
    echo $! > "$WARMUP_PID_FILE"
    wait $!
    rm -f "$WARMUP_PID_FILE"
  ) &
fi

echo "{\"ok\": true, \"audio_path\": \"$WAV_PATH\"}"
