#!/usr/bin/env bash
# scripts/lib_env.sh — 환경 상태 판단 공통 함수 (source 하거나 'status' 인자로 직접 실행)

ms_data_dir() {
  printf '%s' "${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}"
}

ms_venv_python() {
  local d; d="$(ms_data_dir)"
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) printf '%s' "$d/.venv/Scripts/python.exe" ;;
    *) printf '%s' "$d/.venv/bin/python" ;;
  esac
}

ms_python_present() {
  local c
  for c in py python python3; do command -v "$c" &>/dev/null && return 0; done
  return 1
}

ms_env_status() {
  local d vp status_file raw
  d="$(ms_data_dir)"
  vp="$(ms_venv_python)"
  if [ -f "$vp" ] && "$vp" -c "import faster_whisper, sounddevice" 2>/dev/null; then
    printf 'ready'; return
  fi
  status_file="$d/state/setup_status"
  raw=""; [ -f "$status_file" ] && raw="$(cat "$status_file" 2>/dev/null)"
  case "$raw" in
    failed:*) printf 'deps_failed'; return ;;
    installing_deps|downloading_model) printf 'installing'; return ;;
  esac
  if ms_python_present; then printf 'venv_pending'; else printf 'python_missing'; fi
}

ms_env_message() {
  case "$1" in
    python_missing) printf 'Python이 설치되어 있지 않습니다.' ;;
    venv_pending) printf '환경 준비가 필요합니다. 잠시 후 다시 시도하거나, 회의 녹음 시작을 한 번 더 실행해 주세요.' ;;
    installing) printf '환경 설치가 진행 중입니다. 1~2분 후 다시 시도하세요.' ;;
    deps_failed) printf '환경 설치에 실패했습니다. 잠시 후 다시 시도하거나 세션을 새로 시작하세요.' ;;
    *) printf '환경이 준비되지 않았습니다.' ;;
  esac
}

if [ "${BASH_SOURCE[0]}" = "${0}" ] && [ "${1:-}" = "status" ]; then
  ms_env_status; echo
fi
