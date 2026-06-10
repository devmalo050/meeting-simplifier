#!/usr/bin/env bash
# scripts/stop_recording.sh — 녹음 중지
# 출력: JSON {"ok": true, "audio_path": "...", "duration_seconds": N}  또는  {"ok": false, "error": "..."}

PID_DIR="/tmp/meeting-simplifier"
PID_FILE="$PID_DIR/rec.pid"
AUDIO_FILE="$PID_DIR/audio_path"

# rec 프로세스를 SIGTERM → (대기) → SIGKILL 순으로 확실히 종료한다.
# SIGTERM만 보내고 끝내면 안 죽은 rec가 마이크를 계속 점유해 macOS 녹음 인디케이터가 잔존한다.
kill_rec() {
  local pid="$1"
  [ -z "$pid" ] && return
  kill "$pid" 2>/dev/null
  for i in $(seq 1 20); do
    sleep 0.1
    kill -0 "$pid" 2>/dev/null || return
  done
  kill -9 "$pid" 2>/dev/null
  sleep 0.2
}

if [ ! -f "$PID_FILE" ]; then
  # PID 파일이 없어도 고아 rec가 마이크를 점유 중일 수 있으므로 탐색해 정리한다
  ORPHANS=$(pgrep -f "recording_.*\.wav" 2>/dev/null)
  if [ -n "$ORPHANS" ]; then
    for p in $ORPHANS; do kill_rec "$p"; done
    echo '{"ok": false, "error": "녹음 상태가 유실되어 마이크 점유만 해제했습니다. 다시 녹음해 주세요."}'
  else
    echo '{"ok": false, "error": "녹음 중이 아닙니다."}'
  fi
  exit 0
fi

REC_PID=$(cat "$PID_FILE" 2>/dev/null)
WAV_PATH=$(cat "$AUDIO_FILE" 2>/dev/null)

if [ -z "$REC_PID" ] || [ -z "$WAV_PATH" ]; then
  [ -n "$REC_PID" ] && kill_rec "$REC_PID"
  rm -f "$PID_FILE" "$AUDIO_FILE"
  echo '{"ok": false, "error": "녹음 상태 파일이 손상되었습니다."}'
  exit 0
fi

# rec 종료 (WAV 헤더가 올바르게 기록될 때까지 대기 후, 안 죽으면 강제 종료)
kill_rec "$REC_PID"
rm -f "$PID_FILE" "$AUDIO_FILE"

# 파일 존재 확인
if [ ! -f "$WAV_PATH" ]; then
  echo '{"ok": false, "error": "녹음 파일이 생성되지 않았습니다."}'
  exit 0
fi

# 녹음 시간 계산 (sox 사용)
DURATION=$(sox --i -D "$WAV_PATH" 2>/dev/null | python3 -c "import sys; print(round(float(sys.stdin.read().strip()), 1))" 2>/dev/null || echo 0)

echo "{\"ok\": true, \"audio_path\": \"$WAV_PATH\", \"duration_seconds\": $DURATION}"
