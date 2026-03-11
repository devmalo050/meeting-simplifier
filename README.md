# meeting-simplifier

회의를 녹음하고 Whisper + Claude로 회의록을 자동 생성하는 Claude Code 플러그인.

## 기능

- 마이크 녹음 시작/중지
- Whisper large-v3으로 한국어/영어 자동 음성 인식
- Claude로 회의록 자동 생성 (요약, 상세내용, 결정사항, 액션아이템, 트랜스크립트)
- md / txt / docx 포맷 저장
- 자연어 트리거 지원 ("녹음 시작해줘", "회의 끝났어" 등)
- macOS / Windows 지원

## 사전 요구사항

| 의존성 | macOS | Windows |
|--------|-------|---------|
| Node.js 18+ | `brew install node` | [nodejs.org](https://nodejs.org) |
| sox | `brew install sox` | [sourceforge.net/projects/sox](https://sourceforge.net/projects/sox/files/sox/) |
| Python 3.9+ | 기본 설치 | [python.org](https://python.org/downloads) |
| faster-whisper | 플러그인 로드 시 자동 설치 | 플러그인 로드 시 자동 설치 |

> **참고:** 최초 실행 시 Whisper large-v3 모델(약 3GB)이 자동 다운로드됩니다.

> **Windows sox 주의:** Chocolatey sox는 `rec` 바이너리가 누락될 수 있습니다. [공식 sox 바이너리](https://sourceforge.net/projects/sox/files/sox/)를 직접 설치하세요.

## 설치

```bash
# Claude 플러그인 마켓플레이스에서 설치
/plugin install ain/meeting-simplifier
```

또는 로컬에서 직접 사용:
```bash
git clone https://github.com/ain/meeting-simplifier
cd meeting-simplifier
npm install
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

## 설정

`settings.json`에서 변경 가능:

```json
{
  "meeting-simplifier": {
    "output_dir": "~/Documents/meetings",
    "output_format": "md",
    "output_language": "auto"
  }
}
```

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `output_dir` | `~/Documents/meetings` | 회의록 저장 위치 |
| `output_format` | `md` | 출력 포맷 (`md`/`txt`/`docx`) |
| `output_language` | `auto` | 회의록 언어 (`auto`=트랜스크립트 주 언어) |

## 저장 구조

```
~/Documents/meetings/
└── 2026-03-11-분기-마케팅-전략-회의/
    ├── recording.wav      # 녹음 파일
    └── minutes.md         # 회의록
```

## 의존성 확인

```bash
npm run check-deps
```

## 라이선스

MIT
