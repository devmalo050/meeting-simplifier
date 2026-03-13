#!/bin/bash
# scripts/setup.sh — node_modules 및 faster-whisper 자동 설치

# node_modules 설치 (없을 경우)
PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ ! -d "$PLUGIN_ROOT/node_modules" ]; then
  echo "📦 npm 패키지를 설치합니다..."
  cd "$PLUGIN_ROOT" && npm install --quiet
  if [ $? -ne 0 ]; then
    echo "❌ npm install 실패"
  else
    echo "✅ npm install 완료"
  fi
fi

PYTHON_CMD=""

# Python 명령어 탐색
for cmd in python3 python; do
  if command -v "$cmd" &>/dev/null; then
    PYTHON_CMD="$cmd"
    break
  fi
done

if [ -z "$PYTHON_CMD" ]; then
  echo "⚠️  [meeting-simplifier] Python이 설치되어 있지 않습니다."
  echo "   회의 녹음은 가능하지만, 음성 변환 및 회의록 생성이 작동하지 않습니다."
  echo "   Python 3.9 이상이 필요합니다."
  echo "   설치 방법:"
  echo "     macOS: brew install python 또는 https://python.org"
  echo "     Windows: https://python.org/downloads"
  echo "   Python 설치 후 Claude를 재시작하면 자동으로 설정됩니다."
  exit 0
fi

# Python 버전 확인 (3.9 이상 필요)
PY_VERSION=$("$PYTHON_CMD" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$("$PYTHON_CMD" -c "import sys; print(sys.version_info.major)")
PY_MINOR=$("$PYTHON_CMD" -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]; }; then
  echo "⚠️  [meeting-simplifier] Python $PY_VERSION 이 감지되었지만 3.9 이상이 필요합니다."
  echo "   https://python.org/downloads 에서 최신 버전을 설치해주세요."
  exit 0
fi

# faster-whisper 설치 (이미 설치된 경우 pip가 skip)
"$PYTHON_CMD" -c "import faster_whisper" 2>/dev/null
if [ $? -ne 0 ]; then
  echo "📦 faster-whisper를 설치합니다..."
  "$PYTHON_CMD" -m pip install faster-whisper --quiet
  if [ $? -ne 0 ]; then
    echo "❌ faster-whisper 설치 실패. 수동으로 실행하세요: pip install faster-whisper"
  else
    echo "✅ faster-whisper 설치 완료"
  fi
fi
