# 크로스플랫폼(Windows) 지원 설계

**작성일:** 2026-06-09
**브랜치:** `feat/windows-support`
**대상:** `scripts/*`, `hooks/hooks.json`, `commands/*.md`, `README.md`, 신규 `scripts/record.py`·`.ps1`·`.gitattributes`

## 목표

현재 macOS 전용인 meeting-simplifier를 **macOS CLI · macOS 데스크톱 앱 · Windows 데스크톱 앱** 세 환경에서 모두 동작하게 만든다. (크로스플랫폼 Python 코어로 만들므로 Windows CLI도 자연히 포함되나, 명시 타겟은 위 셋이다.)

## 타겟 환경 매트릭스

| 환경 | 현재 | 목표 | 핵심 이슈 |
|------|------|------|-----------|
| macOS + CLI | ✅ 동작 | 회귀 0 | 녹음 엔진 교체분 재검증 |
| macOS + 데스크톱 앱(Code 탭) | ⚠️ 잠재 hang | ✅ | 백그라운드 자식 detach 불완전 시 세션 hang(#43123) |
| Windows + 데스크톱 앱(Code 탭) | ❌ 미동작 | ✅ | 녹음/프로세스 제어/경로/셸 전반 |

**중요 제약(공식 문서 확인):**
- 플러그인은 Claude Desktop 앱의 **Code 탭 + Local 세션**에서만 동작한다. **Chat 탭·Remote 세션에서는 비활성**(슬래시 커맨드가 안 보임).
- **Windows Code 탭은 Git for Windows 설치를 필수로 요구**한다 → Git Bash가 사실상 보장된다. 단 v2.1.139+(2026-05)부터 PowerShell 도구가 Git 설치 환경에서도 옵션으로 점진 롤아웃(`CLAUDE_CODE_USE_POWERSHELL_TOOL`) 중이므로, "항상 Git Bash"를 단정하지 않고 두 셸 모두에서 동작하게 만든다.

## 배경: 현재 코드의 플랫폼 의존성

**macOS 하드코딩 지점**
- `start_recording.sh`: SoX `rec`(CoreAudio 가정), `ps -o comm=`, `pgrep`, `kill -0`, `/tmp/meeting-simplifier` PID 저장, `mktemp`.
- `stop_recording.sh`: `kill`(SIGTERM→SIGKILL) 2단계, `pgrep -f`, `seq`.
- `setup.sh`: `brew install sox`, venv 경로 `bin/python`(:65), Python 탐색 `python3` 우선(:39), `$HOME` 기반 모델 캐시 검사(:96).
- `transcribe.sh:19`: venv `bin/python`.
- `transcribe_server.py:149`: `/tmp/meeting-simplifier` 하드코딩.
- `hooks.json`: 인라인 bash(`nohup`·`/tmp`·`kill -0`·`seq`·`mkdir -p`), setup 훅의 `nohup … >log 2>&1 &`는 **stdin 미차단**.
- `commands/*.md`: `ls -d ~/.claude/plugins/cache/*/…` POSIX glob으로 플러그인 경로 해석.
- `.gitattributes` 부재 → Windows 체크아웃 시 CRLF 셰뱅 깨짐 위험(`#!/bin/bash\r: bad interpreter`).

**데스크톱 앱 특유 제약(리서치로 확인된 실증 버그 포함)**
- **#43123 (데스크톱 앱·Code 모드에서 실증):** SessionStart 훅/Bash가 띄운 백그라운드 자식이 부모의 stdin/stdout/stderr를 물고 있으면, 데스크톱 앱이 stream-json 통신 파이프 점유로 **무응답 hang/타임아웃**(`reason=no_response`). 현재 `rec … &`와 setup `nohup … &`(stdin 누락)가 정확히 이 패턴.
- **#45717:** Bash 도구 타임아웃(기본 120s) 초과 시 SIGTERM이 같은 프로세스 그룹의 **Claude 부모까지** 종료.
- **마이크 권한:** Windows는 "데스크톱 앱이 마이크에 액세스하도록 허용" **단일 그룹 토글**에 종속. 자식 python은 개별 권한 프롬프트를 못 받고, 막히면 친절한 메시지가 아니라 `PortAudio -9999` 에러로 실패.
- **PATH 미상속:** 데스크톱 앱은 셸 프로필 PATH 일부만 상속(Windows는 PowerShell 프로필을 읽지 않음) → python/venv를 **절대경로**로 호출해야 함.
- **자식 생명주기(Windows):** 앱 종료 후 워커 생존(reparenting) 여부 또는 Job Object 강제 종료 여부가 공식 미확인 → 실기 검증 항목.

## 비목표 (Non-goals)

- **WSL2 경로는 별도로 다루지 않는다**(데스크톱 앱 Local 세션 기준). WSL에서도 크로스플랫폼 Python 코어가 동작할 여지는 있으나 명시 타겟 아님.
- **화자 분리·회의록 포맷**은 변경하지 않는다(`transcribe_server.py`의 변환 로직·`save_meeting.py` 포맷 유지, 경로 크로스플랫폼화만).
- **GPU(CUDA) 경로**는 다루지 않는다(현행 CPU int8 유지).
- **"앱 종료 후에도 백그라운드 녹음 지속"을 보장하지 않는다.** 회의 중 Code 탭 세션을 열어두는 사용을 전제로 한다(생존 여부는 검증 후 안내 문구로 처리).

## 아키텍처: "Python 코어 + 얇은 셸 어댑터"

모든 실제 로직(녹음·프로세스 제어·변환·저장)을 OS 비의존 **Python**에 모은다. 셸 스크립트(`.sh`/`.ps1`)는 "venv python을 **절대경로**로 찾아 코어를 호출하는 최소 어댑터"로 축소한다. 결과적으로 POSIX 전용 의존(`/tmp`·`pgrep`·`kill -0`·`ps`·`seq`·glob)이 셸 레이어에서 사라져 Git Bash/PowerShell 어느 쪽이든 동작한다.

## 핵심 설계 결정

### 1. 녹음 엔진: SoX/ffmpeg 외부 바이너리 제거 → Python `sounddevice`로 단일화
- `sounddevice.InputStream`(PortAudio 휠 번들, 외부 설치 불요)으로 48kHz/mono/16bit 녹음, 표준 `wave`로 직접 기록. macOS의 `rec`도 교체(`setup.sh`의 `brew install sox` 삭제). **단일 녹음 코드**.
- Windows finalize·신호·`pgrep` 함정이 **설계적으로 소멸**(Python이 직접 WAV를 닫음).

### 2. 데스크톱 앱 안전 detach (최우선 — #43123/#45717 회피)
- 새 파일 `scripts/record.py`가 녹음 워커를 **self-spawn**하되, **stdin=DEVNULL, stdout/stderr=로그 파일, 새 프로세스 그룹**으로 완전 분리:
  - POSIX: `start_new_session=True`
  - Windows: `creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW`
- `record.py start`: 워커를 백그라운드로 넘기고 **즉시** `{"ok":true,"audio_path":...}` 출력 후 종료(120s 타임아웃 무관, 부모 파이프 비점유).
- `hooks.json`의 setup 훅도 `</dev/null`을 추가(현재 stdin 누락 — macOS 데스크톱 앱에서도 잠재 hang).

### 3. 녹음 중지: stop 플래그 파일 (OS 신호 의존 제거)
- `record.py stop`: data 디렉토리에 **stop 플래그 파일** 생성 → 워커가 폴링하다 감지하면 루프 종료 + WAV 정상 close → duration 계산해 JSON 출력. 미응답 시에만 `psutil`로 최후 종료(고아 정리 책임은 플러그인이 짐).

### 4. 상태 경로: `/tmp` 추방 → data 디렉토리 절대경로
- PID·audio_path·stop.flag·result·transcript를 `~/.claude/plugins/data/meeting-simplifier-meeting-simplifier/state/` 절대경로에 보관 → 셸·OS 무관 공유(Git Bash `/tmp`는 가상경로라 PowerShell 전환 시 불일치).

### 5. venv·Python·모델 캐시 크로스플랫폼화
- venv python: **절대경로** + `bin/python`(POSIX) ↔ `Scripts\python.exe`(Windows) 분기(`setup.sh:65`, `transcribe.sh:19`, 신규 `.ps1`).
- Python 탐색: Windows는 `py`→`python`, POSIX는 현행 `python3`→`python`.
- **HF_HOME을 data 디렉토리 아래로 고정** → git-bash `$HOME`↔Python `USERPROFILE` 불일치로 인한 재다운로드 차단. setup·transcribe 양쪽에서 동일 export.

### 6. 마이크 권한 실패의 친절한 보고
- 워커 시작 시 입력 디바이스 **probe** → PortAudio 에러(`-9999` 등)를 잡아 "Windows 설정 > 개인정보 보호 및 보안 > 마이크 > '데스크톱 앱이 마이크에 액세스하도록 허용'을 켜세요" 한국어 안내로 변환. 워커는 detach돼 stdout이 끊겼으므로 **result 파일에 기록**, stop/start가 읽어 사용자에게 전달.

### 7. 커맨드 경로 해석: POSIX glob 제거
- `${CLAUDE_PLUGIN_ROOT}`는 커맨드 `.md`에서 미주입(기존 선례)이나 **hooks에서는 동작**한다. SessionStart 훅이 플러그인 루트를 data 파일(예: `state/plugin_root`)에 기록 → 커맨드는 그 파일을 읽어 Python을 절대경로로 호출. `ls -d … glob`·`sort -V`·`tail` 제거. 커맨드는 bash·PowerShell 양쪽 코드블록 제공.

### 8. 셸 런처 + 훅
- `setup.sh`(POSIX/Git Bash) + 신규 `setup.ps1`(PowerShell): Python 탐색→venv→`pip install faster-whisper sounddevice psutil python-docx`→모델 다운로드. macOS `brew install sox` 제거. Windows는 `winget`/python.org 안내(Microsoft Store Python 배제 — venv/pip 깨짐).
- 신규 `start_recording.ps1`·`stop_recording.ps1`·`transcribe.ps1`(얇은 어댑터).
- `hooks.json`: SessionStart/SessionEnd를 `"shell":"bash"`/`"powershell"` 엔트리로 분리.

### 9. 위생
- 신규 `.gitattributes`: `*.sh text eol=lf`(CRLF 셰뱅 깨짐 방지), 셰뱅 `#!/usr/bin/env bash` 통일.
- `uninstall.sh` Windows 경로 보강 + 신규 `uninstall.ps1`.

## 파일별 변경 계획

**신규**
- `scripts/record.py` — sounddevice 녹음 코어(start/stop/worker), 안전 detach, 마이크 probe, stop 플래그.
- `scripts/setup.ps1`, `scripts/start_recording.ps1`, `scripts/stop_recording.ps1`, `scripts/transcribe.ps1`, `scripts/uninstall.ps1` — PowerShell 어댑터.
- `.gitattributes`.

**수정**
- `scripts/start_recording.sh`·`stop_recording.sh` → `record.py` 호출 얇은 어댑터로 축소.
- `scripts/setup.sh` — sox 제거, venv 경로/Python 탐색/HF_HOME OS 분기.
- `scripts/transcribe.sh` — venv 절대경로 분기.
- `scripts/transcribe_server.py` — `/tmp`→data 경로, HF_HOME 반영(변환 로직 불변).
- `scripts/save_meeting.py` — 경로 점검(이미 pathlib, 거의 무변경).
- `scripts/cleanup_old_versions.sh`·`uninstall.sh` — Windows 경로 보강.
- `hooks/hooks.json` — shell 분기, `</dev/null` 추가, `/tmp`·POSIX 의존 제거, plugin_root 기록.
- `commands/start.md`·`stop.md`·`summarize.md` — glob 제거, bash/PowerShell 양쪽, Python 절대경로 호출.
- `README.md` — 3환경 지원 명시, "Code 탭 + Local 세션", 마이크 권한 안내, Windows 설치(winget).

## 검증 체크리스트 (실기 — 사용자 Windows PC)

1. Code 탭 + Local 세션에서 `/meeting-simplifier:start|stop|summarize` 인식·실행. Remote 세션에서는 비활성 확인.
2. Bash 도구가 Git Bash인지 PowerShell인지 판별(`uname -a` vs `$PSVersionTable`). `CLAUDE_CODE_USE_POWERSHELL_TOOL` 기본값 실측.
3. detach 불완전 시 세션 hang 재현 → 완전 detach 적용 후 hang 소멸 확인(#43123).
4. 120s 초과 명령이 부모 세션을 죽이지 않는지, 런처가 즉시 리턴하는지(#45717).
5. 마이크 토글 3종(기기/앱/데스크톱 앱) ON·OFF 조합별 녹음 성공·실패와 PortAudio 에러 메시지·한국어 안내 확인.
6. 앱/세션 종료 후 워커 생존(reparenting) vs 강제 종료(Job Object), stop 플래그 정상 종료.
7. PATH/venv 미상속 대비 — `.venv/Scripts/python.exe` 절대경로 실행, 필요 시 settings.json env로 PATH 명시.
8. 커맨드 plugin_root 해석이 Git Bash·PowerShell 양쪽에서 정확한지.
9. SessionStart(setup)·SessionEnd(정리) 훅이 Windows Code 탭에서 정상 타이밍 실행, SessionEnd 조기 kill 없는지.
10. **macOS 회귀 검증**(CLI + 데스크톱 앱): 녹음 엔진 교체분 정상 동작.

## 리스크 및 완화

| 리스크 | 심각도 | 완화 |
|--------|--------|------|
| detach 불완전 → 데스크톱 세션 hang(#43123) | 치명 | stdin/stdout/stderr 전부 차단 + 새 프로세스 그룹, 런처 즉시 리턴 |
| Windows 워커 생명주기 불확실(앱 종료 시 사멸 가능) | 중 | 회의 중 세션 유지 전제 + 검증 후 안내. stop 플래그/PID로 정리 책임 |
| 마이크 단일 토글·PortAudio -9999 | 중 | probe 선검사 + 한국어 안내를 result 파일로 보고 |
| PATH/venv 미상속 | 중 | python 절대경로 호출, Scripts 경로 분기 |
| 녹음 엔진 교체로 macOS 회귀 | 중 | TDD로 `record.py` 코어 우선 검증 + macOS 실기 회귀 |
| CRLF 셰뱅 깨짐 | 중 | `.gitattributes` eol=lf, `#!/usr/bin/env bash` |
| Chat 탭/Remote 세션 오사용 | 낮 | README에 "Code 탭 + Local 세션" 명시 |

## 참고 출처(핵심)

- Claude Code 데스크톱/설치/도구/훅 공식 문서: `code.claude.com/docs/en/{desktop,setup,tools-reference,hooks}`
- 데스크톱 앱 세션 hang(백그라운드 stdin 점유): GitHub anthropics/claude-code #43123, 타임아웃 부모 종료 #45717
- Windows 마이크 권한: Microsoft Support(데스크톱 앱 그룹 토글), python-sounddevice #293(PortAudio -9999)
- venv 경로/Python 런처/HF 캐시: docs.python.org(venv·Windows), huggingface.co(HF_HOME)
