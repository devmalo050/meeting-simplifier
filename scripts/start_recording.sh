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
rec -q -r 48000 -c 1 -b 16 -e signed-integer "$WAV_PATH" &
REC_PID=$!

# 프로세스 확인
sleep 0.3
if ! kill -0 "$REC_PID" 2>/dev/null; then
  echo '{"ok": false, "error": "녹음 시작에 실패했습니다."}'
  exit 0
fi

echo "$REC_PID" > "$PID_FILE"
echo "$WAV_PATH" > "$AUDIO_FILE"

# warmup: 무음 1초짜리 wav로 --oneshot 실행 → 모델을 OS 페이지 캐시에 올림
# 녹음하는 동안 백그라운드에서 완료되므로 변환 시점엔 이미 캐시됨
VENV_PYTHON="$PLUGIN_ROOT/.venv/bin/python"
WHISPER_MODEL="${WHISPER_MODEL:-medium}"
WARMUP_DONE="$PID_DIR/warmup.done"

if [ -f "$VENV_PYTHON" ] && [ ! -f "$WARMUP_DONE" ]; then
  (
    # 무음 1초 wav 생성 (sox)
    DUMMY_WAV=$(mktemp /tmp/warmup-XXXX.wav)
    sox -n -r 16000 -c 1 -b 16 "$DUMMY_WAV" trim 0.0 1.0 2>/dev/null
    if [ -f "$DUMMY_WAV" ]; then
      WHISPER_MODEL="$WHISPER_MODEL" "$VENV_PYTHON" \
        "$PLUGIN_ROOT/scripts/transcribe_server.py" \
        --oneshot "$DUMMY_WAV" >/dev/null 2>&1
      rm -f "$DUMMY_WAV"
      touch "$WARMUP_DONE"
    fi
  ) &
fi

echo "{\"ok\": true, \"audio_path\": \"$WAV_PATH\"}"
