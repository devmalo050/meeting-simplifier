#!/bin/bash
# scripts/stop_recording.sh — 녹음 중지
# 출력: JSON {"ok": true, "audio_path": "...", "duration_seconds": N}  또는  {"ok": false, "error": "..."}

PID_DIR="/tmp/meeting-simplifier"
PID_FILE="$PID_DIR/rec.pid"
AUDIO_FILE="$PID_DIR/audio_path"

if [ ! -f "$PID_FILE" ]; then
  echo '{"ok": false, "error": "녹음 중이 아닙니다."}'
  exit 0
fi

REC_PID=$(cat "$PID_FILE" 2>/dev/null)
WAV_PATH=$(cat "$AUDIO_FILE" 2>/dev/null)

if [ -z "$REC_PID" ] || [ -z "$WAV_PATH" ]; then
  rm -f "$PID_FILE" "$AUDIO_FILE"
  echo '{"ok": false, "error": "녹음 상태 파일이 손상되었습니다."}'
  exit 0
fi

# rec 종료
kill "$REC_PID" 2>/dev/null
# WAV 헤더가 올바르게 기록될 때까지 대기
for i in $(seq 1 20); do
  sleep 0.1
  kill -0 "$REC_PID" 2>/dev/null || break
done

rm -f "$PID_FILE" "$AUDIO_FILE"

# 파일 존재 확인
if [ ! -f "$WAV_PATH" ]; then
  echo '{"ok": false, "error": "녹음 파일이 생성되지 않았습니다."}'
  exit 0
fi

# 녹음 시간 계산 (파일 크기 기반: rate=16000, channels=1, bits=16)
FILE_SIZE=$(stat -f%z "$WAV_PATH" 2>/dev/null || stat -c%s "$WAV_PATH" 2>/dev/null || echo 44)
HEADER_SIZE=44
DATA_SIZE=$((FILE_SIZE - HEADER_SIZE))
if [ "$DATA_SIZE" -lt 0 ]; then DATA_SIZE=0; fi
# bytes / (rate * channels * bytes_per_sample) = seconds
DURATION=$(python3 -c "print(round($DATA_SIZE / (16000 * 1 * 2), 1))" 2>/dev/null || echo 0)

echo "{\"ok\": true, \"audio_path\": \"$WAV_PATH\", \"duration_seconds\": $DURATION}"
