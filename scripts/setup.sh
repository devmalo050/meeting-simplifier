#!/bin/bash
# scripts/setup.sh — sox, faster-whisper(venv), python-docx 자동 설치

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# ── 중복 실행 방지 ──────────────────────────────────────────────────────────
LOCK_FILE="/tmp/meeting-simplifier-setup.lock"
if [ -f "$LOCK_FILE" ]; then
  exit 0
fi
trap 'rm -f "$LOCK_FILE"' EXIT
touch "$LOCK_FILE"

# ── 1. SoX 설치 (녹음에 필요) ──────────────────────────────────────────────
if ! command -v rec &>/dev/null; then
  if command -v brew &>/dev/null; then
    echo "📦 SoX를 설치합니다 (brew install sox)..."
    brew install sox --quiet
    [ $? -eq 0 ] && echo "✅ SoX 설치 완료" || echo "❌ SoX 설치 실패. 수동으로 실행하세요: brew install sox"
  elif command -v apt-get &>/dev/null; then
    echo "📦 SoX를 설치합니다 (apt-get)..."
    sudo apt-get install -y sox libsox-fmt-all -qq
  elif command -v choco &>/dev/null; then
    echo "📦 SoX를 설치합니다 (choco)..."
    choco install sox --yes --quiet
  else
    echo "⚠️  SoX가 없습니다. 녹음 기능이 작동하지 않습니다."
    echo "   설치: brew install sox (macOS) / apt install sox (Linux)"
  fi
fi

# ── 2. Python 확인 ─────────────────────────────────────────────────────────
PYTHON_CMD=""
for cmd in python3 python; do
  if command -v "$cmd" &>/dev/null; then
    PYTHON_CMD="$cmd"
    break
  fi
done

if [ -z "$PYTHON_CMD" ]; then
  echo "⚠️  Python이 없습니다. 음성 변환 기능이 작동하지 않습니다."
  echo "   설치: brew install python (macOS) / https://python.org"
  exit 0
fi

PY_MAJOR=$("$PYTHON_CMD" -c "import sys; print(sys.version_info.major)")
PY_MINOR=$("$PYTHON_CMD" -c "import sys; print(sys.version_info.minor)")
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]; }; then
  echo "⚠️  Python $PY_MAJOR.$PY_MINOR 감지 — 3.9 이상이 필요합니다."
  exit 0
fi

WHISPER_MODEL="${WHISPER_MODEL:-medium}"

# ── 3. venv 생성 및 패키지 설치 ─────────────────────────────────────────────
VENV_DIR="$PLUGIN_ROOT/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
  echo "📦 Python 가상환경을 생성합니다..."
  "$PYTHON_CMD" -m venv "$VENV_DIR"
  if [ $? -ne 0 ]; then
    echo "❌ venv 생성 실패"
    exit 0
  fi
  echo "✅ 가상환경 생성 완료"
fi

# faster-whisper가 venv에 없으면 설치
if ! "$VENV_PYTHON" -c "import faster_whisper" 2>/dev/null; then
  echo "📦 faster-whisper를 설치합니다..."
  "$VENV_PYTHON" -m pip install faster-whisper --quiet
  [ $? -eq 0 ] && echo "✅ faster-whisper 설치 완료" || echo "❌ faster-whisper 설치 실패. 수동으로 실행하세요: pip install faster-whisper"
fi

# python-docx가 venv에 없으면 설치
if ! "$VENV_PYTHON" -c "import docx" 2>/dev/null; then
  echo "📦 python-docx를 설치합니다..."
  "$VENV_PYTHON" -m pip install python-docx --quiet
  [ $? -eq 0 ] && echo "✅ python-docx 설치 완료" || echo "❌ python-docx 설치 실패"
fi

# ── 4. Whisper 모델 미리 다운로드 ─────────────────────────────────────────
MODEL_CACHE="$HOME/.cache/huggingface/hub/models--Systran--faster-whisper-${WHISPER_MODEL}"
if [ ! -d "$MODEL_CACHE" ]; then
  echo "📦 Whisper ${WHISPER_MODEL} 모델을 다운로드합니다 (최초 1회)..."
  "$VENV_PYTHON" -c "from faster_whisper import WhisperModel; WhisperModel('${WHISPER_MODEL}', device='cpu', compute_type='int8')" 2>/dev/null
  [ $? -eq 0 ] && echo "✅ Whisper ${WHISPER_MODEL} 모델 준비 완료" || echo "⚠️  모델 다운로드 실패 (첫 번째 변환 시 자동 다운로드됩니다)"
fi
