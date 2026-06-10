#!/usr/bin/env bash
# scripts/setup.sh — venv + faster-whisper + sounddevice 자동 설치 (POSIX/Git Bash)

DATA_DIR="${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}"
LOCK_FILE="$DATA_DIR/setup.lock"
mkdir -p "$DATA_DIR"

if [ -f "$LOCK_FILE" ]; then
  LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null)
  if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
    exit 0
  fi
fi
trap 'rm -f "$LOCK_FILE"' EXIT
echo $$ > "$LOCK_FILE"

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) IS_WIN=1 ;;
  *) IS_WIN=0 ;;
esac

if [ "$IS_WIN" = "1" ]; then CANDIDATES="py python python3"; else CANDIDATES="python3 python"; fi
PYTHON_CMD=""
for cmd in $CANDIDATES; do
  if command -v "$cmd" &>/dev/null; then PYTHON_CMD="$cmd"; break; fi
done
if [ -z "$PYTHON_CMD" ]; then
  echo "⚠️  Python이 없습니다. Windows: winget install -e --id Python.Python.3.12 / macOS: brew install python"
  exit 1
fi

PY_OK=$("$PYTHON_CMD" -c "import sys; print(1 if sys.version_info[:2] >= (3,9) else 0)" 2>/dev/null)
if [ "$PY_OK" != "1" ]; then
  echo "⚠️  Python 3.9 이상이 필요합니다."
  exit 1
fi

VENV_DIR="$DATA_DIR/.venv"
if [ "$IS_WIN" = "1" ]; then VENV_PYTHON="$VENV_DIR/Scripts/python.exe"; else VENV_PYTHON="$VENV_DIR/bin/python"; fi

if [ ! -f "$VENV_PYTHON" ]; then
  echo "📦 Python 가상환경을 생성합니다..."
  "$PYTHON_CMD" -m venv "$VENV_DIR" || { echo "❌ venv 생성 실패"; exit 1; }
fi

if ! "$VENV_PYTHON" -c "import faster_whisper, sounddevice, psutil, numpy" 2>/dev/null; then
  echo "📦 핵심 의존성을 설치합니다 (faster-whisper, sounddevice, psutil, numpy)..."
  "$VENV_PYTHON" -m pip install --quiet faster-whisper sounddevice psutil numpy \
    || { echo "❌ 핵심 의존성 설치 실패. 수동: pip install faster-whisper sounddevice psutil numpy"; exit 1; }
fi

if ! "$VENV_PYTHON" -c "import docx" 2>/dev/null; then
  "$VENV_PYTHON" -m pip install --quiet python-docx \
    && echo "✅ python-docx 설치 완료" || echo "⚠️  python-docx 설치 실패 (docx 출력만 영향, md/txt는 정상)"
fi

export HF_HOME="$DATA_DIR/hf"
WHISPER_MODEL="${WHISPER_MODEL:-medium}"
MODEL_CACHE="$HF_HOME/hub/models--Systran--faster-whisper-${WHISPER_MODEL}"

# 구버전(~/.cache/huggingface)에 받아둔 모델이 있으면 신규 HF_HOME으로 1회 이전 — 업그레이드 시 재다운로드 방지
OLD_HF_HUB="$HOME/.cache/huggingface/hub"
if [ ! -d "$MODEL_CACHE" ] && [ -d "$OLD_HF_HUB" ]; then
  mkdir -p "$HF_HOME/hub"
  for m in "$OLD_HF_HUB"/models--Systran--faster-whisper-*; do
    [ -d "$m" ] && mv "$m" "$HF_HOME/hub/" 2>/dev/null && echo "기존 모델을 이전했습니다: $(basename "$m")"
  done
fi

if [ ! -d "$MODEL_CACHE" ]; then
  echo "📦 Whisper ${WHISPER_MODEL} 모델을 다운로드합니다 (최초 1회)..."
  HF_HOME="$HF_HOME" "$VENV_PYTHON" -c "from faster_whisper import WhisperModel; WhisperModel('${WHISPER_MODEL}', device='cpu', compute_type='int8')" 2>/dev/null \
    && echo "✅ 모델 준비 완료" || echo "⚠️  모델 다운로드 실패 (첫 변환 시 자동 시도)"
fi

if [ -n "$MS_SETUP_MARKER" ] && "$VENV_PYTHON" -c "import faster_whisper, sounddevice, psutil, numpy" 2>/dev/null; then
  touch "$MS_SETUP_MARKER"
fi
