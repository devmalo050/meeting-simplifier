#!/usr/bin/env bash
# scripts/install_python.sh — Python 탐지 후 없으면 설치(Windows winget). JSON status 출력.

for cmd in py python python3; do
  if command -v "$cmd" &>/dev/null; then
    printf '%s\n' '{"ok": true, "status": "python_present", "message": "Python이 이미 설치되어 있습니다."}'
    exit 0
  fi
done

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    if command -v winget &>/dev/null; then
      if MSYS_NO_PATHCONV=1 winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements; then
        printf '%s\n' '{"ok": true, "status": "python_installed_restart_needed", "message": "Python을 설치했습니다. (UAC 권한 창이 떴다면 \"예\"를 누르셨을 겁니다.) 적용을 위해 Claude 세션을 완전히 새로 시작한 뒤 다시 \"회의 녹음 시작\"을 해주세요."}'
        exit 0
      else
        printf '%s\n' '{"ok": false, "status": "python_install_failed", "message": "Python 자동 설치에 실패했습니다. https://www.python.org/downloads/windows/ 에서 Python을 설치(설치 화면에서 Add python.exe to PATH 체크)한 뒤 Claude 세션을 새로 시작해주세요."}'
        exit 1
      fi
    else
      printf '%s\n' '{"ok": false, "status": "python_missing_no_winget", "message": "Python과 winget이 모두 없습니다. https://www.python.org/downloads/windows/ 에서 Python을 설치(Add python.exe to PATH 체크)한 뒤 Claude 세션을 새로 시작해주세요."}'
      exit 1
    fi
    ;;
  Darwin)
    printf '%s\n' '{"ok": false, "status": "python_missing", "message": "Python이 없습니다. brew install python 으로 설치한 뒤 다시 시도하세요."}'
    exit 1
    ;;
  *)
    printf '%s\n' '{"ok": false, "status": "python_missing", "message": "Python이 없습니다. 배포판 패키지(예: apt install python3)로 설치한 뒤 다시 시도하세요."}'
    exit 1
    ;;
esac
