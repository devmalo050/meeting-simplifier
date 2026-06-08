# meeting-simplifier

회의를 녹음하고 Whisper + Claude로 회의록을 자동 생성하는 Claude Code 플러그인.

## 기능

- 마이크 녹음 시작/중지
- Whisper medium으로 한국어/영어 자동 음성 인식 (언어 자동 감지)
- Claude로 회의록 자동 생성 (요약, 상세내용, 결정사항, 액션아이템, 트랜스크립트)
- md / txt / docx 포맷 저장
- 자연어 트리거 지원 ("녹음 시작해줘", "회의 끝났어" 등)
- macOS 지원

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
| Claude Code (CLI 또는 데스크톱) | 위 명령을 실행할 환경 |
| macOS | 현재 macOS만 지원 |
| Homebrew | `sox`(녹음) 자동 설치에 사용 — [brew.sh](https://brew.sh) |
| Python 3.9+ | 보통 macOS에 기본 내장 |

`sox`·`faster-whisper`·Whisper 모델(약 1.5GB)은 **설치 후 첫 세션에서 플러그인이 자동으로 내려받습니다.** 직접 설치할 필요 없습니다.

### 설치 후 첫 사용

새 Claude Code 세션에서 채팅에 한마디면 됩니다:

- **"회의 녹음 시작해줘"** → 회의가 끝나면 **"회의 끝났어"**
- 생성된 회의록은 `~/Documents/meetings/`에 자동 저장됩니다.

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

## 동작 기본값

현재 버전은 아래 값으로 고정되어 동작합니다 (별도 설정은 지원하지 않습니다).

| 항목 | 값 |
|------|------|
| 저장 위치 | `~/Documents/meetings` (쓰기 권한 없으면 `~/Desktop`으로 대체) |
| 출력 포맷 | Markdown (`.md`) |
| 회의록 언어 | 트랜스크립트의 주 언어 |
| 음성 인식 모델 | Whisper `medium` (환경변수 `WHISPER_MODEL`로 변경 가능) |

## 저장 구조

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

이 스크립트는 모델 캐시 · 임시 파일 · 가상환경 · 설치 마커를 지웁니다. **회의록(`~/Documents/meetings`)은 보존됩니다.**

다음은 수동 정리가 필요합니다:
- 마켓플레이스 등록 해제: `/plugin marketplace remove meeting-simplifier`
- macOS 마이크 권한: 시스템 설정 > 개인정보 보호 및 보안 > 마이크 에서 해당 앱(터미널/Claude) 항목 정리

## 라이선스

MIT
