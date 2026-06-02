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

VENV_PYTHON="$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier/.venv/bin/python"
# venv 디렉토리만 있고 패키지가 안 깔린 반쪽 설치 상태를 import 가능 여부로 정확히 걸러낸다
if [ ! -f "$VENV_PYTHON" ] || ! "$VENV_PYTHON" -c "import faster_whisper" 2>/dev/null; then
  echo '{"error": "환경이 아직 준비되지 않았습니다. 의존성 설치가 끝난 뒤 다시 시도하세요."}'
  exit 1
fi

WHISPER_MODEL="${WHISPER_MODEL:-medium}"

# 변환 실행 (모델이 OS 페이지 캐시에 있으면 빠름)
WHISPER_MODEL="$WHISPER_MODEL" "$VENV_PYTHON" \
  "$PLUGIN_ROOT/scripts/transcribe_server.py" \
  --oneshot "$AUDIO_PATH"
