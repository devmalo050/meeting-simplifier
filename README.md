# meeting-simplifier

회의를 녹음하고 Whisper + Claude로 회의록을 자동 생성하는 Claude Code 플러그인.

## 기능

- 마이크 녹음 시작/중지
- Whisper medium으로 한국어/영어 자동 음성 인식 (언어 자동 감지)
- Claude로 회의록 자동 생성 (요약, 상세내용, 결정사항, 액션아이템, 트랜스크립트)
- md / txt / docx 포맷 저장
- 자연어 트리거 지원 ("녹음 시작해줘", "회의 끝났어" 등)
- macOS · Windows 지원 (Claude Desktop 앱 Code 탭 / CLI)

## 설치

한 번이면 끝납니다. 아래 셋 중 편한 방법 하나만 고르세요.

### A. 터미널 한 줄 — 가장 빠름

```bash
claude plugin marketplace add devmalo050/meeting-simplifier && claude plugin install meeting-simplifier@meeting-simplifier
```

### B. Claude 채팅에 붙여넣기

Claude Code 채팅창에 아래를 그대로 붙여넣으세요:

```
devmalo050/meeting-simplifier 저장소를 플러그인 마켓플레이스로 추가하고
meeting-simplifier 플러그인을 설치해줘.
```

설치 중 권한 요청이 뜨면 허용하면 됩니다.

### C. `/plugin` 메뉴에서 클릭

1. 채팅에 `/plugin` 입력
2. **Add marketplace** → `devmalo050/meeting-simplifier`
3. 목록에서 `meeting-simplifier` → **Install**

> 로컬에서 직접 쓰려면: `git clone https://github.com/devmalo050/meeting-simplifier`

### 설치 전 준비물

| 필요한 것 | 비고 |
|---|---|
| Claude Code (CLI 또는 데스크톱 앱) | Windows는 **데스크톱 앱의 Code 탭 + Local 세션**에서 동작 (Chat 탭·Remote 세션 불가) |
| Windows: Git for Windows | 데스크톱 앱 Code 탭이 요구 — 설치 시 Git Bash 포함 |
| Python 3.9+ | macOS 기본 내장 / Windows: `winget install -e --id Python.Python.3.12` (Microsoft Store 버전은 비권장) |

`sounddevice`·`faster-whisper`·Whisper 모델(약 1.5GB)은 설치 후 첫 세션에서 플러그인이 자동으로 내려받습니다. SoX 등 외부 녹음 도구는 더 이상 필요 없습니다.

### 설치 후 첫 사용

새 Claude Code 세션에서 채팅에 한마디면 됩니다:

- **"회의 녹음 시작해줘"** → 회의가 끝나면 **"회의 끝났어"**
- 생성된 회의록은 기본 폴더(macOS `~/Documents/meetings/`, Windows `~/Desktop/meetings/`)에 자동 저장됩니다. 저장 위치를 바꾸려면 "회의록 저장 위치 바꿔줘"라고 말하세요([상세](#회의록-저장-위치-바꾸기)).

## 사용법

### 명령어

| 명령어 | 동작 |
|--------|------|
| `/meeting-simplifier:start` | 녹음 시작 |
| `/meeting-simplifier:stop` | 녹음 중지 + 회의록 생성 |
| `/meeting-simplifier:summarize [파일경로]` | 기존 파일로 회의록 생성 |

### 자연어

- "회의 녹음 시작해줘" / "start recording"
- "녹음 끝" / "회의 끝났어" / "end meeting"
- "이 파일 회의록으로 정리해줘"

## Windows 첫 실행 (Python 자동 설치)

Python이 없는 새 PC라면, 처음 **"회의 녹음 시작"** 할 때 플러그인이 Python 설치를 안내합니다:
1. Python을 자동 설치합니다. **권한(UAC) 창이 뜨면 "예"**를 눌러주세요.
2. 설치 후 **Claude 세션을 완전히 새로 시작**하세요(설치된 Python을 인식하기 위함 — Windows 특성).
3. 다시 "회의 녹음 시작"을 하면 나머지(음성 인식 의존성·모델)가 자동으로 준비됩니다.

winget이 없는 환경이면 [python.org](https://www.python.org/downloads/windows/)에서 Python을 설치(설치 화면에서 "Add python.exe to PATH" 체크)한 뒤 세션을 새로 시작하세요.

## Windows에서 마이크가 안 잡힐 때

Windows는 데스크톱 앱 전체에 마이크 권한을 한 번에 부여합니다. 녹음이 실패하면:
**설정 > 개인정보 보호 및 보안 > 마이크** 에서
`마이크 액세스`, `앱이 마이크에 액세스하도록 허용`, `데스크톱 앱이 마이크에 액세스하도록 허용` 세 가지를 모두 켜세요.

## 회의록 저장 위치 바꾸기

회의록은 기본적으로 macOS는 `~/Documents/meetings`, Windows는 `~/Desktop/meetings` 아래에 저장됩니다. 다른 폴더로 바꾸려면 그냥 말로 요청하세요.

- 변경: "회의록 저장 위치 바꿔줘" 또는 "회의록 바탕화면에 저장해줘"
- 확인: "회의록 지금 어디에 저장돼?"
- 초기화: "회의록 저장 위치 원래대로 돌려줘"

설정한 폴더는 이후 모든 회의록에 계속 적용됩니다(어느 위치에서 녹음하든 동일).

## 동작 기본값

| 항목 | 기본값 |
|------|------|
| 저장 위치 | macOS `~/Documents/meetings` · Windows `~/Desktop/meetings` (쓰기 권한 없으면 `~/Desktop`으로 대체, 자연어로 변경 가능) |
| 출력 포맷 | Markdown (`.md`) |
| 회의록 언어 | 트랜스크립트의 주 언어 |
| 음성 인식 모델 | Whisper `medium` (환경변수 `WHISPER_MODEL`로 변경 가능) |

## 저장 구조

기본 폴더(macOS `~/Documents/meetings`, Windows `~/Desktop/meetings`) 아래에 회의별로 생성됩니다.

```
~/Documents/meetings/
└── 2026-03-11-143052-분기-마케팅-전략-회의/
    ├── 분기-마케팅-전략-회의.wav   # 녹음 파일
    └── 분기-마케팅-전략-회의.md    # 회의록
```

## 제거

플러그인을 삭제해도 Whisper 모델 캐시(약 1.9GB) 등 일부 잔여물이 시스템에 남습니다. 완전히 정리하려면:

```bash
bash ~/.claude/plugins/cache/*/meeting-simplifier/*/scripts/uninstall.sh
# 로컬 클론을 쓴 경우: bash <클론경로>/scripts/uninstall.sh
```

이 스크립트는 모델 캐시 · 임시 파일 · 가상환경 · 설치 마커를 지웁니다. **회의록(macOS `~/Documents/meetings`, Windows `~/Desktop/meetings`)은 보존됩니다.**

다음은 수동 정리가 필요합니다:
- 마켓플레이스 등록 해제: `/plugin marketplace remove meeting-simplifier`
- macOS 마이크 권한: 시스템 설정 > 개인정보 보호 및 보안 > 마이크 에서 해당 앱(터미널/Claude) 항목 정리

## 라이선스

MIT
