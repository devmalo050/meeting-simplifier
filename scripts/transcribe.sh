#!/usr/bin/env bash
# scripts/transcribe.sh — 오디오 → 텍스트 (record.py와 동일 venv 사용)
PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AUDIO_PATH="$1"
DATA_DIR="${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}"
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) VENV_PYTHON="$DATA_DIR/.venv/Scripts/python.exe" ;;
  *) VENV_PYTHON="$DATA_DIR/.venv/bin/python" ;;
esac

if [ -z "$AUDIO_PATH" ]; then echo '{"error": "audio_path가 필요합니다."}'; exit 1; fi
if [ ! -f "$AUDIO_PATH" ]; then echo "{\"error\": \"파일이 없습니다: $AUDIO_PATH\"}"; exit 1; fi
if [ ! -f "$VENV_PYTHON" ] || ! "$VENV_PYTHON" -c "import faster_whisper" 2>/dev/null; then
  echo '{"error": "환경이 아직 준비되지 않았습니다. 의존성 설치가 끝난 뒤 다시 시도하세요."}'; exit 1
fi

export HF_HOME="$DATA_DIR/hf"
WHISPER_MODEL="${WHISPER_MODEL:-medium}" HF_HOME="$HF_HOME" "$VENV_PYTHON" \
  "$PLUGIN_ROOT/scripts/transcribe_server.py" --oneshot "$AUDIO_PATH"
