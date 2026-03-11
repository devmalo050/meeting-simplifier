# Meeting Simplifier — Claude 플러그인 설계 문서

**작성일:** 2026-03-11
**상태:** 승인됨

---

## 개요

회의를 녹음하고 녹음된 파일 기반으로 회의록을 자동 생성하는 Claude Code 플러그인.
Claude Desktop, VS Code Claude 익스텐션, Claude Code CLI에서 모두 사용 가능.

---

## 아키텍처

### 플러그인 구조

```
meeting-simplifier/
├── .claude-plugin/
│   └── plugin.json           # 플러그인 메타데이터
├── mcp-server/
│   ├── index.js              # MCP 서버 진입점
│   ├── recorder.js           # 마이크 녹음 (node-record-lpcm16)
│   ├── transcriber.js        # Whisper 호출 (subprocess)
│   └── exporter.js           # md/txt/docx 파일 저장
├── skills/
│   ├── start/SKILL.md        # 녹음 시작
│   ├── stop/SKILL.md         # 녹음 중지 + 회의록 생성
│   └── summarize/SKILL.md    # 기존 오디오/텍스트 파일로 회의록 생성
├── .mcp.json                 # MCP 서버 연결 설정
├── settings.json             # 기본 설정값
└── package.json
```

### 데이터 흐름

```
사용자 → Skill(/meeting-simplifier:start/stop) 또는 자연어
       → Claude가 MCP 도구 호출
       → MCP 서버: 마이크 녹음 → WAV 파일 (임시 저장)
       → MCP 서버: Whisper large로 트랜스크립트 생성
       → Claude: 트랜스크립트 받아 회의 제목 생성 + 회의록 구성
       → MCP 서버: 회의 디렉토리 생성 후 녹음파일 + 회의록 저장
```

---

## MCP 서버 상세

### 런타임
- Node.js 18+
- 크로스플랫폼 (macOS, Windows)

### 제공 도구

| 도구 | 설명 |
|------|------|
| `meeting_record_start` | 마이크 녹음 시작 |
| `meeting_record_stop` | 녹음 중지, WAV 파일 경로 반환 |
| `meeting_transcribe` | WAV → 텍스트 (Whisper large, 자동 언어 감지) |
| `meeting_save` | 회의 제목 디렉토리 생성 후 녹음파일 + 회의록 저장 |

### 녹음
- 라이브러리: `node-record-lpcm16`
- 포맷: WAV, 16kHz, mono (Whisper 최적 입력)
- 임시 저장: `os.tmpdir()`
- 의존성: `sox` (macOS: Homebrew, Windows: Chocolatey)

### Whisper STT
- 구현: `faster-whisper` (Python)를 Node.js subprocess로 호출
- 모델: `large` **고정 (변경 불가)**
- 언어: `auto` (한국어/영어 자동 감지)
- 긴 녹음(1시간+): 청크 단위로 분할 처리

### 파일 저장
- 저장 경로: `{output_dir}/{YYYY-MM-DD-회의제목}/`
  - 예: `~/Documents/meetings/2026-03-11-분기-마케팅-전략-회의/`
- 해당 디렉토리에 녹음 파일(WAV) + 회의록 파일 함께 저장
- 회의 제목: Claude가 트랜스크립트 내용을 보고 생성
- 출력 포맷: `md` (기본), `txt`, `docx` 지원
- DOCX 생성: `docx` npm 패키지

---

## Skills

| Skill | 명령어 | 동작 |
|-------|--------|------|
| `start` | `/meeting-simplifier:start` | 녹음 시작 안내 + `meeting_record_start` 호출 |
| `stop` | `/meeting-simplifier:stop` | 녹음 중지 → 트랜스크립트 → 회의록 생성 → 저장 |
| `summarize` | `/meeting-simplifier:summarize [파일경로]` | 기존 오디오/텍스트 파일로 회의록 생성 |

자연어로도 트리거 가능 (예: "회의 녹음 시작해줘", "녹음 끝내고 회의록 만들어줘")

---

## 회의록 구성

```markdown
# 회의 제목

**일시:** YYYY-MM-DD HH:mm
**참석자:** (발화자 감지된 경우)
**언어:** 한국어 / 영어

---

## 요약
(핵심 내용 간략히)

## 상세 내용
(주제별로 논의된 내용 정리, 회의 길이에 맞게)

## 결정 사항
- ...

## 액션 아이템
| 담당자 | 내용 | 기한 |
|--------|------|------|
| ...    | ...  | ...  |

## 발화 내용
(Speaker A, Speaker B 등으로 구분 — Claude가 문맥으로 추정)

## 전체 트랜스크립트
(Whisper 원문 그대로)
```

**Speaker Diarization:** Whisper는 화자 구분 미지원. Claude가 트랜스크립트 문맥으로 화자 추정. 향후 `pyannote-audio` 연동 확장 포인트 유지.

---

## 설정

`settings.json`:

```json
{
  "meeting-simplifier": {
    "output_dir": "~/Documents/meetings",
    "output_format": "md",
    "output_language": "auto"
  }
}
```

| 설정 | 기본값 | 변경 가능 | 설명 |
|------|--------|-----------|------|
| `output_dir` | `~/Documents/meetings` | ✅ | 회의록 저장 위치 |
| `output_format` | `md` | ✅ (`md`/`txt`/`docx`) | 출력 포맷 |
| `output_language` | `auto` | ✅ (`auto`/`ko`/`en`) | 회의록 작성 언어 |
| `whisper_model` | `large` | ❌ 고정 | Whisper 모델 |

---

## 사전 설치 요구사항

| 의존성 | macOS | Windows |
|--------|-------|---------|
| Node.js 18+ | `brew install node` | winget/공식 사이트 |
| sox | `brew install sox` | `choco install sox` |
| Python 3.8+ | 기본 설치 | 공식 사이트 |
| faster-whisper | `pip install faster-whisper` | `pip install faster-whisper` |

---

## 에러 처리

| 상황 | 처리 방식 |
|------|-----------|
| 마이크 접근 권한 없음 | 명확한 에러 메시지 + OS별 권한 설정 안내 |
| `sox` 미설치 | 설치 방법 안내 메시지 |
| `faster-whisper` 미설치 | 설치 방법 안내 메시지 |
| 녹음 중 중단 (Ctrl+C 등) | 임시 파일 정리 후 종료 |
| 트랜스크립트 결과 빈 값 | "음성이 감지되지 않았습니다" 안내 |
| 파일 저장 권한 없음 | 대체 경로 제안 (바탕화면 등) |
| 긴 녹음 (1시간+) | Whisper 청크 단위 분할 처리 |

---

## 지원 플랫폼

- macOS (Apple Silicon / Intel)
- Windows 10/11
