#!/bin/bash
# scripts/uninstall.sh — 플러그인이 자기 디렉토리 밖에 남긴 잔여물을 정리한다.
# Claude Code의 플러그인 삭제는 cache 디렉토리만 지우므로, 모델 캐시(~1.9GB) 등은 수동 정리가 필요하다.
# 회의록(~/Documents/meetings)은 사용자 데이터이므로 절대 삭제하지 않는다.
set -u

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "meeting-simplifier 잔여물 정리를 시작합니다."
echo "(회의록 ~/Documents/meetings 은 삭제하지 않습니다)"
echo ""

remove() {
  local target="$1"
  local label="$2"
  if [ -e "$target" ]; then
    echo "🗑  $label: $target"
    rm -rf "$target"
  fi
}

# Whisper 모델 캐시 (가장 큰 잔여물, medium 약 1.4GB + small 약 0.5GB)
for d in "$HOME"/.cache/huggingface/hub/models--Systran--faster-whisper-*; do
  [ -e "$d" ] && remove "$d" "Whisper 모델 캐시"
done

# 런타임 상태 / 락 / warmup 임시파일
remove "/tmp/meeting-simplifier" "런타임 상태 디렉토리"
remove "/tmp/meeting-simplifier-setup.lock" "setup 락"
for w in /tmp/warmup-*.wav; do
  [ -e "$w" ] && remove "$w" "warmup 임시 wav"
done

# 설치 완료 마커 + 로그 + 가상환경 (data 디렉토리에 통합 저장됨)
remove "$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier" "설치 마커/로그/가상환경"

# 구버전이 버전 폴더 안에 만들던 .venv 잔여물 (v1.4.16 이하)
for v in "$HOME"/.claude/plugins/cache/*/meeting-simplifier/*/.venv; do
  [ -d "$v" ] && remove "$v" "구버전 가상환경 잔여물"
done

# 로컬 클론(소스)에서 직접 쓴 경우의 가상환경
remove "$PLUGIN_ROOT/.venv" "로컬 가상환경"

echo ""
echo "✅ 정리 완료."
echo ""
echo "다음은 자동으로 정리되지 않으므로 필요 시 수동 처리하세요:"
echo "  • 마켓플레이스 등록 해제:  /plugin marketplace remove meeting-simplifier"
echo "  • macOS 마이크 권한:  시스템 설정 > 개인정보 보호 및 보안 > 마이크 에서 해당 앱(터미널/Claude) 항목 정리"
echo "  • 빈 임시 폴더:  ~/.claude/plugins/marketplaces/temp_* (호스트 CLI가 남긴 빈 클론)"
