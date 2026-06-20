# Windows Python 자동 설치 + 결정론적 온보딩 설계

**작성일:** 2026-06-20
**브랜치:** `feat/onboarding-python`
**대상:** `scripts/setup.sh`, `scripts/start_recording.sh`, `scripts/stop_recording.sh`, `scripts/transcribe.sh`, `commands/*.md`, 신규 `scripts/install_python.sh`, `scripts/record.py`(status 헬퍼)

## 목표

완전 새 Windows PC(Python 미설치)에서 플러그인을 처음 쓸 때, Claude가 오류를 보며 즉흥적으로 winget을 실행하는 trial-and-error 대신 **결정론적이고 가이드된 설치 흐름**으로 Python·의존성이 준비되게 한다. 동일 입력에 동일 동작.

## 배경: 현재 문제

- `setup.sh:27-30`은 Python이 없으면 `winget install ...` **문구만 echo하고 `exit 1`** — 실제 설치를 하지 않는다.
- `start_recording.sh`/`transcribe.sh`는 환경 미준비를 **단일 문자열**(`"환경이 아직 준비되지 않았습니다"`)로만 보고 → Claude가 "준비 중 / Python 아예 없음 / 설치 실패"를 구분 못 하고 임의로 winget을 친다.
- 결과: 매번 다른 즉흥 명령(trial-and-error). 사용자가 지적한 "막 오류 맞으면서 알아서 해결"이 정확히 이 빈틈에서 발생.

## 리서치 핵심 (공식 문서 검증)

- **OS 제약(high):** Windows에서 Python 설치 후 PATH는 레지스트리에 영구 반영되나, **이미 실행 중인 세션은 환경 스냅샷만 유지**해 새 PATH를 못 본다(MS: Raymond Chen, child-process 환경 상속). → "설치 → 같은 세션 즉시 사용"은 결정론적으로 불가, **세션 1회 재시작이 필수**.
- **UAC:** winget으로 Python(classic) 설치는 `--scope user`여도 UAC 프롬프트가 뜰 수 있다(winget-cli #3285). 완전 무인 불가 → 설치는 **사용자 가시 시점**(녹음 시작)에 트리거하고 "UAC 창이 뜨면 예"를 안내.
- **훅 출력 비신뢰:** SessionStart 훅의 stdout/additionalContext는 사용자 UI에 직접 안 보이고, 플러그인 additionalContext 미전달 버그(#16538, closed not planned)·신규 대화 stdout 드롭(#13650/#10373)이 있다. → 진행 안내를 훅 출력에 의존하지 말고, **커맨드가 상태 파일을 읽어 보고**.
- **allowed-tools 비신뢰:** 커맨드 프런트매터 allowed-tools enforcement가 보장되지 않음(#18837). → "winget 금지"를 제약으로 막지 말고, **설치 책임을 결정론 스크립트에 두고** 커맨드 지시문으로 유도.
- **Python 패키지:** 2026 공식 권장은 winget의 Python Install Manager(pymanager)이나 venv 호환 미검증 → 보수적으로 **classic `Python.Python.3.12`**(현 `.venv/Scripts/python.exe` 가정과 검증된 호환).

## 결정 사항

| 결정 | 선택 | 근거 |
|------|------|------|
| 자동화 강도 | **자동 설치** | 사용자 의도. winget으로 직접 설치 |
| 타겟 환경 | **개인 Win10/11 위주** | winget 가정, 없으면 단일 안내(폴백 단순) |
| Python 패키지 | **classic Python.Python.3.12** | venv 호환 검증됨. pymanager는 보류 |
| 설치 트리거 | **사용자 가시 시점(녹음 시작)** | UAC 창을 사용자가 봐야 함, 백그라운드 hang 회피 |
| 설치 후 | **세션 1회 재시작 안내** | OS 제약(PATH 미반영) |
| LLM 통제 | **스크립트 책임 + 커맨드 지시문** | allowed-tools 비신뢰 |

## 비목표 (Non-goals)

- winget 부재 환경의 완전 자동화(python.org silent 폴백)는 하지 않는다 — 단일 안내로 갈음(개인 PC 위주).
- pymanager(Python Install Manager) 경로는 이번에 도입하지 않는다(venv 호환 미검증).
- PreToolUse 가드로 winget 직접 호출을 강제 차단하지 않는다(데스크톱 미발화·오버헤드 대비 이득 작음).
- 녹음/변환/회의록 로직은 변경하지 않는다(상태 보고 계층만 추가).

## 아키텍처

### 1. `scripts/install_python.sh` (신규, Python 설치 단일 책임)

```
1) py → python → python3 탐지. 발견 시 {"ok":true,"status":"python_present"} 출력하고 종료.
2) 미발견 + Windows(uname MINGW/MSYS/CYGWIN):
   - command -v winget 있음:
       winget install -e --id Python.Python.3.12 --silent \
         --accept-package-agreements --accept-source-agreements
       성공 → {"ok":true,"status":"python_installed_restart_needed",
               "message":"Python을 설치했습니다. UAC 창이 떴다면 '예'를 누르셨을 겁니다.
                          Claude 세션을 새로 시작한 뒤 다시 '회의 녹음 시작'을 해주세요."}
       실패 → {"ok":false,"status":"python_install_failed","message":"...수동 안내..."}
   - winget 없음:
       {"ok":false,"status":"python_missing_no_winget",
        "message":"Python이 없고 winget도 없습니다. python.org 또는 Microsoft Store에서
                   Python을 설치하고 Claude 세션을 새로 시작해주세요."}
3) 미발견 + macOS/Linux:
   {"ok":false,"status":"python_missing",
    "message":"Python이 없습니다. macOS: brew install python / Linux: apt install python3 후 다시 시도하세요."}
```
- 설치 직후 같은 세션 PATH 미반영을 전제로, 절대 즉시 venv 생성을 시도하지 않는다(restart 안내가 안전망).

### 2. 환경 상태 보고 (status 계층)

- `setup.sh`: 단계 진입 시 `STATE_DIR/setup_status` 파일 갱신 — `installing_deps` → `downloading_model` → `ready`(또는 `failed:<사유>`). 종료 시 정상이면 `ready`.
- `record.py`에 헬퍼 `env_status()` 추가: venv python 존재 + 핵심 import 가능 여부, `setup_status` 파일, Python 존재를 종합해 다음 열거형 반환:
  - `ready` — venv·의존성 준비됨
  - `python_missing` — venv 없고 Python도 없음
  - `installing` — `setup_status`가 installing_deps/downloading_model
  - `deps_failed` — `setup_status`가 failed:*
  - `venv_pending` — Python은 있으나 venv/의존성 아직(설치 시작 유도)
- `start_recording.sh`/`transcribe.sh`: venv 미준비 시 단일 error 대신 `record.py env-status`(또는 자체 점검)로 `{"ok":false,"status":"...","message":"..."}` 반환. venv 준비됐으면 기존 동작.

### 3. 커맨드 결정론 분기 (`start.md`/`stop.md`/`summarize.md`)

start_recording.sh 결과의 `status`별로 Claude에게 고정 지시:
- `ready` → 정상 녹음 안내.
- `python_missing` → "**반드시 `install_python.sh`만 실행**하라. winget/python/pip 명령을 직접 조합하지 말 것." 실행 후 결과 `message`를 사용자에게 그대로 전달(특히 `python_installed_restart_needed`면 세션 재시작 안내).
- `venv_pending` → "환경 준비를 시작합니다(`setup.sh`만 호출). 잠시 후 다시 시도하세요."
- `installing` → "환경 준비 중입니다. 1~2분 후 다시 시도하세요"만 안내. **직접 설치 금지.**
- `deps_failed` → `message`를 그대로 전달하고 중단.
- 공통 지시문: "위 status에 따라 정해진 행동만 하라. 임의의 winget/pip/python 설치 명령을 만들지 말 것."

### 4. 부트스트랩 진입점

- SessionStart 훅: 현행 fire-and-forget detach(`</dev/null`) 유지. Python이 **있으면** 의존성/모델 자동 설치(현행), **없으면** `setup_status=python_missing`만 기록하고 종료(백그라운드 UAC hang 회피 — Python 설치는 훅에서 하지 않는다).
- 실제 Python 설치(UAC 동반)는 사용자가 "녹음 시작"하는 **가시 시점**에 커맨드가 `install_python.sh`를 호출해 트리거.

### 5. macOS 영향

- macOS는 Python이 보통 존재 → install_python.sh가 1단계에서 `python_present` 반환, 기존 흐름 유지. 상태 보고 계층만 크로스플랫폼 공통 적용. 회귀 위험 낮음.

## 파일별 변경 계획

**신규**
- `scripts/install_python.sh` — Python 탐지/설치 단일 책임, JSON status 반환.
- `tests/test_install_python.py` 또는 `tests/test_env_status.py` — status 매핑 단위 테스트.

**수정**
- `scripts/setup.sh` — Python 없을 때 echo+exit 대신 `setup_status=python_missing` 기록; 단계별 `setup_status` 갱신; 종료 시 `ready`.
- `scripts/record.py` — `env_status()` 헬퍼 + `env-status` 서브커맨드 추가.
- `scripts/start_recording.sh`/`transcribe.sh` — venv 미준비 시 status+message JSON 반환.
- `commands/start.md`/`stop.md`/`summarize.md` — status별 결정론 분기 + "정해진 스크립트만 호출" 지시문.
- `README.md` — Windows 첫 실행 시 "Python 자동 설치 → UAC 예 → 세션 재시작" 흐름 안내.
- `.claude-plugin/plugin.json`/`marketplace.json` — 버전 1.5.0 → 1.5.1.

## 검증

- **단위(macOS):** install_python.sh의 Python 탐지/분기(모킹), record.py `env_status()` 열거형 매핑, setup.sh setup_status 전이.
- **회귀(macOS):** Python 존재 환경에서 기존 녹음→변환→저장 정상.
- **실기(Windows, 사용자):** Python 미설치 새 PC에서 "녹음 시작" → `python_missing` → install_python.sh → winget 설치(UAC 예) → 세션 재시작 → 자동 의존성·모델 → 녹음 성공. winget 없는 환경에서 단일 안내 노출.

## 리스크

| 리스크 | 완화 |
|--------|------|
| winget 설치 후 같은 세션 PATH 미반영 | 즉시 venv 시도 금지, "세션 재시작" 결정론 안내 |
| winget UAC 프롬프트로 완전 무인 불가 | 가시 시점 트리거 + "UAC 예" 사전 안내 |
| 백그라운드 훅에서 UAC hang | Python 설치를 훅에서 하지 않음(가시 시점만) |
| LLM이 지시 무시하고 winget 직접 실행 | 설치 책임을 스크립트에 + 커맨드 지시문(allowed-tools 비신뢰) |
| classic 3.12 장기 deprecated(3.16+) | 한시적 선택, 추후 pymanager 검증 시 전환(문서 명시) |
| status 계층 추가로 기존 흐름 회귀 | venv 준비 시 기존 동작 그대로, status는 미준비 경로에만 |
