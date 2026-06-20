# HANDOFF — Windows Python 자동설치 + 결정론적 온보딩 (feat/onboarding-python)
<!-- 작성: 2026-06-20 -->

## 🔥 핫 스테이트 (여기만 읽어도 재개 가능)
- **목표**: 완전 새 Windows PC(Python 미설치)에서 플러그인 첫 사용 시, Claude가 오류를 보며 즉흥적으로 winget을 치는 trial-and-error 대신, **결정론적·가이드된 흐름**으로 Python·의존성이 설치되게 한다.
- **현재 상태**: `feat/onboarding-python` 브랜치에 구현·검증 **완료**(main 대비 10커밋, 작업트리 clean). 단위 테스트 **30 passed**. macOS에서 ready 경로 실제 녹음 e2e 통과. 최종 다차원 리뷰의 high·medium 결함까지 반영 완료. **아직 main 미머지 / 미푸시.**
- **바로 다음 할 일**:
  1. `finishing-a-development-branch` 마무리 — 사용자에게 4옵션(main 로컬 merge / push+PR / 유지 / 폐기) 중 선택받아 실행. (직전 작업 패턴은 "merge→push로 1.5.x 정식 배포"였음)
  2. main 머지·push 후, 사용자 환경 플러그인 갱신: `claude plugin marketplace update meeting-simplifier && claude plugin update meeting-simplifier@meeting-simplifier` → **새 세션**에서 적용.
  3. **Task 8(Windows 실기 검증)은 사용자 몫** — 플랜 파일의 Task 8 체크리스트 참고(Python 없는 새 PC에서 "녹음 시작" → python_missing → install_python.sh → winget 설치(UAC 예) → 세션 재시작 → 자동 의존성·모델 → 녹음).
- **블로커**: 없음. Windows 실기 검증만 사용자 대기(이전 1.5.0 Windows 검증은 사용자가 "잘된다" 확인함).

## 변경 사항 (이번 세션) — 모두 feat/onboarding-python, main 미머지
- `scripts/lib_env.sh` (신규) — 환경 상태 열거형 판단 공통 셸. 함수: `ms_data_dir`/`ms_venv_python`(uname 분기)/`ms_python_present`/`ms_env_status`/`ms_env_message`. `status` 인자로 CLI 실행, source 시 함수만 정의(BASH_SOURCE 가드).
- `scripts/install_python.sh` (신규) — Python 탐지(py→python→python3) 후 없으면 Windows winget으로 classic `Python.Python.3.12` 설치. JSON status 반환(python_present/python_installed_restart_needed/python_install_failed/python_missing_no_winget/python_missing).
- `scripts/setup.sh` — 단계별 `state/setup_status` 전이(installing_deps→downloading_model→ready), Python 부재 시 python_missing 기록, **실패 exit 3곳에서 `failed:<사유>` 기록**(최종 리뷰 high fix).
- `scripts/start_recording.sh` / `scripts/transcribe.sh` — lib_env source 후 venv 미준비 시 `{"ok":false,"status":"...","message":"..."}` JSON 보고(단일 error 문자열 제거).
- `commands/start.md` — status별 결정론 분기(ok:true / ok:false(status없음) / python_missing→install_python.sh만 / venv_pending→nohup setup.sh / installing / deps_failed). "임의 winget/pip/python 금지" 명문화.
- `commands/stop.md` / `commands/summarize.md` — transcribe 결과 status+ok:false 분기 추가(python_missing이면 install_python.sh만, 나머지는 message 전달).
- `scripts/lib_env.sh` (재수정) — `ms_env_message(venv_pending)`에서 "설치를 시작합니다" 제거(stop/summarize는 실제 setup 안 함 → 메시지-동작 모순이었음). 따옴표 없이 JSON-안전 유지.
- `tests/test_env_shell.py` (신규) — lib_env status 4분기 + install_python python_present 테스트(pytest subprocess).
- `README.md` — "Windows 첫 실행 (Python 자동 설치)" 섹션 추가.
- `.claude-plugin/plugin.json` / `marketplace.json` — 1.5.0 → **1.5.1** (둘 다).
- `docs/superpowers/specs/2026-06-20-onboarding-python-install-design.md` (신규) — 설계 스펙.
- `docs/superpowers/plans/2026-06-20-onboarding-python.md` (신규) — 8태스크 구현 플랜.

## 결정과 이유
- **자동 설치(winget) 채택** — 사용자가 "안내만"이 아니라 "설치되도록"을 명시 요청. 기각: Claude 가이드 전용(수동 설치 마찰 큼).
- **classic Python.Python.3.12 사용** — 현 `.venv/Scripts/python.exe` 가정과 검증된 호환. 기각: 2026 공식 권장 pymanager(venv 호환 미검증이라 보류 — 추후 검증 시 전환, classic은 3.16+ 미생산이라 한시적).
- **설치 후 "세션 1회 재시작" 안내가 필수** — Windows는 이미 실행 중인 세션이 새 PATH를 못 봄(MS 공식: Raymond Chen, child-process 환경 스냅샷). "설치→같은 세션 즉시 사용"은 결정론적으로 불가. 기각: 같은 세션 즉시 venv 생성(PATH 미반영으로 실패).
- **Python 설치는 SessionStart 훅(백그라운드) 아닌 "녹음 시작"(사용자 가시 시점)에 트리거** — winget UAC 프롬프트를 사용자가 봐야 함, 백그라운드 detach에서 UAC hang 위험(winget-cli #3285).
- **LLM 통제는 allowed-tools 아닌 "스크립트 책임 + 커맨드 지시문"** — 커맨드 프런트매터 allowed-tools enforcement 비신뢰(anthropic/claude-code #18837). 설치를 install_python.sh에 캡슐화하고 "그 스크립트만 호출" 지시 → LLM 자유도가 "스크립트 호출 여부"로 좁혀짐.
- **환경 상태 판단을 record.py(Python) 아닌 lib_env.sh(셸)로** — Python이 없을 때 Python 스크립트를 못 돌리므로 상태 판단은 셸이어야 함.
- **winget 없는 환경은 단일 안내로 갈음** — 타겟 "개인 Win10/11 위주". python.org silent 폴백 자동화는 비목표(분기·보안 복잡도 대비 이득 작음).

## 막다른 길 / 실패한 시도
- (이전 1.5.0 작업) 플랜 리뷰어가 "hooks.json `shell` 필드가 스키마에 없다(오탐)"고 critical 제기 → 공식 문서(code.claude.com/docs/en/hooks) 직접 확인 결과 **`"shell":"bash"|"powershell"` 필드는 실재**. 다만 Windows Code 탭이 Git for Windows 필수라 Git Bash 보장 → bash 단일 경로로 단순화(PowerShell 어댑터 미작성). 교훈: 로컬 plugin-dev SKILL.md보다 최신 공식 레퍼런스 우선.
- (이번 세션) 서브에이전트 구현 직후엔 보이지 않던 결함을 **최종 다차원 리뷰가 reproduce로 적발**: ① setup.sh 실패 시 `failed:*` 미기록 → deps_failed가 dead code → "설치 중" 무한 루프(high), ② stop/summarize의 venv_pending이 "설치를 시작합니다"라 하고 실제 안 함(medium). 둘 다 수정 완료(`7fbf97a`). 교훈: 태스크별 리뷰는 통합/시나리오 결함을 못 잡음 → 최종 전체 리뷰 필수.

## 원시 데이터 (그대로)
- 최종 테스트: `.venv/bin/python -m pytest tests/ -q` → `30 passed in 2.12s` (record.py 25 + test_env_shell.py 5).
- high fix 검증: `setup_status`에 `failed:핵심 의존성 설치 실패` 기록 후 `bash scripts/lib_env.sh status` → `deps_failed` (이전엔 `installing_deps` 잔존 → `installing` 무한반복).
- ready 경로 녹음 e2e(macOS, 심볼릭 venv): start `{"ok": true, "audio_path": ".../recording_20260620_134144.wav"}`, stop `{"ok": true, ..., "duration_seconds": 2.3}`.
- 환경 status 실동작: venv없음+python있음→`venv_pending`, setup_status=installing_deps→`installing`, failed:*→`deps_failed`, 심볼릭 venv→`ready`.
- 버전: `plugin.json 1.5.1 / marketplace.json 1.5.1 / MATCH`.
- ms_env_message 4종 전부 `printf '{"message":"%s"}'` 임베드 시 JSON 유효(따옴표 없음).
- 현재 사용자 설치 상태(직전 세션): 정식 설치는 **1.5.0**(GitHub devmalo050/meeting-simplifier 경유, enabled). data venv는 1.5.0 기준.

## 열린 스레드 / 블로커
- Task 8 Windows 실기 검증 미완(사용자 대기) — 특히 winget UAC 동반 설치, 설치 후 세션 재시작, winget 없는 환경의 python_missing_no_winget 안내 노출.
- low 미해결(출시 차단 아님): install_python.sh winget 종료코드 0만 성공 처리(이미설치 시 비0 오분류 가능, speculative); ms_env_status가 매 호출 무거운 import 검증(체감 지연 가능); setup.sh의 python_missing 기록값을 ms_env_status case가 안 봄(라이브 체크로 폴스루 — 동작은 옳으나 dead coupling).

## 다음 단계 (순서대로)
1. **브랜치 마무리** — `finishing-a-development-branch`로 사용자에게 4옵션 제시. 테스트 30 passed·작업트리 clean·일반 repo·base=main 이미 확인됨.
2. 사용자가 머지 선택 시: `git checkout main && git merge --ff-only feat/onboarding-python` → `git push origin main` → `git branch -d feat/onboarding-python`.
3. 사용자 플러그인 갱신: `claude plugin marketplace update meeting-simplifier && claude plugin update meeting-simplifier@meeting-simplifier` (적용은 새 세션).
4. **사용자**: 새 Windows PC에서 Task 8 체크리스트 실기 검증. 실패 항목은 해당 스크립트/커맨드로 회귀 수정 후 1.5.2.

## 핵심 파일 / 위치
- `scripts/lib_env.sh:22` — `ms_env_status`(환경 status 5값 판단의 단일 진실원천).
- `scripts/lib_env.sh:38` — `ms_env_message`(어댑터 JSON에 임베드 — 따옴표 금지).
- `scripts/install_python.sh` — Python 설치 단일 책임, JSON status 반환.
- `scripts/setup.sh:39,49,56` — 실패 시 `set_status "failed:..."`(high fix 핵심).
- `commands/start.md:20-43` — status별 결정론 분기(LLM trial-and-error 차단의 핵심).
- `docs/superpowers/plans/2026-06-20-onboarding-python.md` — Task 8(Windows 실기 검증 체크리스트) 포함.

## 실행 / 테스트
- 테스트: `.venv/bin/python -m pytest tests/ -q` (루트에서).
- 셸 문법: `bash -n scripts/*.sh`.
- 환경 status 수동: `MS_DATA_DIR=/tmp/x bash scripts/lib_env.sh status`.
- 로컬 브랜치 플러그인 시험(머지·푸시 없이): `claude --plugin-dir /Users/ain/Projects/meeting-simplifier` (단 디렉토리가 해당 브랜치 체크아웃 상태여야 함; 기존 설치와 충돌 시 `claude plugin disable meeting-simplifier@meeting-simplifier` 후 시험, 끝나면 enable 복구).

## 참조 (복제 금지, 경로/URL만)
- 설계 스펙: `docs/superpowers/specs/2026-06-20-onboarding-python-install-design.md`
- 구현 플랜(Task 1-8): `docs/superpowers/plans/2026-06-20-onboarding-python.md`
- 직전 작업(1.5.0 크로스플랫폼/데스크톱앱 지원) 스펙·플랜: `docs/superpowers/specs/2026-06-09-windows-support-design.md`, `docs/superpowers/plans/2026-06-09-windows-support.md`
- 데스크톱앱/훅 함정 메모리: `~/.claude/projects/-Users-ain-Projects-meeting-simplifier/memory/reference_claude_plugin_windows_desktop.md`
- 저장소: github.com/devmalo050/meeting-simplifier (main = 1.5.0 배포됨)
