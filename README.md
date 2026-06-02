# meeting-simplifier

회의를 녹음하고 Whisper + Claude로 회의록을 자동 생성하는 Claude Code 플러그인.

## 기능

- 마이크 녹음 시작/중지
- Whisper medium으로 한국어/영어 자동 음성 인식 (언어 자동 감지)
- Claude로 회의록 자동 생성 (요약, 상세내용, 결정사항, 액션아이템, 트랜스크립트)
- md / txt / docx 포맷 저장
- 자연어 트리거 지원 ("녹음 시작해줘", "회의 끝났어" 등)
- macOS 지원

## 사전 요구사항

| 의존성 | macOS |
|--------|-------|
| sox | `brew install sox` |
| Python 3.9+ | 기본 설치 |
| faster-whisper | 플러그인 로드 시 자동 설치 |

> **참고:** 최초 실행 시 Whisper medium 모델(약 1.5GB)이 자동 다운로드됩니다.

## 설치

```bash
# 1) 마켓플레이스 등록
/plugin marketplace add devmalo050/meeting-simplifier
# 2) 플러그인 설치
/plugin install meeting-simplifier@meeting-simplifier
```

또는 로컬에서 직접 사용:
```bash
git clone https://github.com/devmalo050/meeting-simplifier
```

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
