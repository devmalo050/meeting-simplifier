#!/usr/bin/env bash
# scripts/cleanup_old_versions.sh
# 호스트(Claude Code)는 버전 업데이트 시 옛 버전 폴더(cache/.../<version>/)를 자동 삭제하지 않는다.
# 이 스크립트는 "현재 실행 중인 버전"만 남기고 같은 플러그인의 옛 버전 폴더를 정리한다.
#
# 안전 원칙(자기 상위 캐시를 rm -rf 하므로 엄격히 적용):
#  - 삭제 후보는 semver 버전 디렉토리만 — 비버전 사용자 데이터(docs/notes/src 등)를 원천 배제.
#  - 경로는 물리 경로(cd -P/pwd -P)로 정규화하고, 현재 버전은 inode 동일성(-ef)으로 보존
#    (심볼릭 링크 별칭 경유 호출 시 현재 실행 버전이 삭제되는 것을 방지).
#  - 정식 Claude 캐시 설치 루트(~/.claude/plugins/cache/<marketplace>/meeting-simplifier) 하위일 때만 동작.
#    로컬 클론 / marketplaces 설치 / 비정상 경로에서는 아무 일도 하지 않는다.
set -u

CURRENT_ROOT="$(cd -P "$(dirname "$0")/.." && pwd -P)"

# 안전장치 1: 빈/위험 경로면 중단
case "$CURRENT_ROOT" in
  "" | "/" | "$HOME") exit 0 ;;
esac

PARENT="$(dirname "$CURRENT_ROOT")"
CUR_VER="$(basename "$CURRENT_ROOT")"

# 안전장치 2: 현재 버전 디렉토리명이 semver가 아니면(비정상 호출) 중단
case "$CUR_VER" in
  [0-9]*.[0-9]*.[0-9]*) : ;;
  *) exit 0 ;;
esac

# 안전장치 3: 정식 Claude 캐시 설치 루트 하위가 아니면(로컬 클론·marketplaces 등) 중단
# Git Bash(Windows)에서도 동일 경로($HOME/.claude/plugins/cache/...)로 매칭되어 동작한다.
case "$PARENT" in
  "$HOME"/.claude/plugins/cache/*/meeting-simplifier) : ;;
  *) exit 0 ;;
esac

# 형제 버전 폴더만 정리: semver 디렉토리이고, 현재 버전(inode 기준)이 아니고, 심볼릭 링크가 아닌 것
for d in "$PARENT"/*/; do
  d="${d%/}"
  [ -d "$d" ] || continue
  [ -L "$d" ] && continue
  name="$(basename "$d")"
  [ "$name" = "$CUR_VER" ] && continue
  case "$name" in [0-9]*.[0-9]*.[0-9]*) : ;; *) continue ;; esac
  [ "$d" -ef "$CURRENT_ROOT" ] && continue
  echo "옛 버전 정리: $d"
  rm -rf "$d"
done
