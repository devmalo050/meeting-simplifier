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
| `meeting_transcribe` | WAV/MP3/M4A → 텍스트 (Whisper large, 자동 언어 감지) |
| `meeting_save` | 회의 제목 디렉토리 생성 후 녹음파일 + 회의록 저장 |

### 도구 파라미터 & 반환값 스키마

```
meeting_record_start()
  → { ok: true } | { error: string }

meeting_record_stop()
  → { audio_path: string } | { error: string }
  // error 케이스: "no active recording"

meeting_transcribe({ audio_path: string })
  → { transcript: string, language: "ko"|"en" } | { error: string }
  // 지원 입력 포맷: WAV, MP3, M4A
  // Whisper large-v3 사용
  // 모델 캐시: ~/.cache/huggingface/ (약 3GB, 최초 실행 시 다운로드)
  // 1시간+ 녹음: 10분 청크로 분할, 30초 오버랩, 순서대로 재결합

meeting_save({
  title: string,        // Claude가 생성한 회의 제목
  transcript: string,   // Whisper 원문
  minutes: string,      // Claude가 생성한 회의록 본문
  audio_path: string,   // 임시 WAV 경로
  format: "md"|"txt"|"docx"
})
  → { saved_dir: string } | { error: string }
```

### MCP 서버 상태 관리
녹음은 프로세스 내 전역 변수로 상태 유지:
```js
let activeRecording = null; // { stream, tempPath } | null
```
- `start` 호출 시 이미 녹음 중이면 에러 반환
- `stop` 호출 시 녹음 없으면 에러 반환
- MCP 서버 재시작 시 임시 파일 정리 후 상태 초기화

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

### 자연어 트리거 패턴

Skill의 `description` 필드에 다양한 트리거 패턴을 정의해 Claude가 자동 인식하도록 함.

**`start` skill 트리거 예시 (한국어):**
- "회의 녹음 시작해줘 / 해" / "녹음 시작" / "녹음해줘"
- "회의 시작할게" / "미팅 시작해" / "회의 시작"
- "지금부터 회의 녹음" / "회의 들어갈게"
- "record meeting" / "start recording" / "start meeting"

**`stop` skill 트리거 예시:**
- "녹음 끝" / "녹음 종료" / "녹음 멈춰" / "녹음 중지"
- "회의 끝났어" / "미팅 종료" / "회의 마칠게"
- "회의록 만들어줘" / "회의록 정리해줘"
- "stop recording" / "end meeting" / "finish recording"

**`summarize` skill 트리거 예시:**
- "이 파일 회의록으로 정리해줘" / "녹음 파일 분석해줘"
- "파일 첨부할게, 회의록 만들어줘"
- "summarize this recording" / "make minutes from this file"

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
- ...
- ...

## 발화 내용
(Speaker A, Speaker B 등으로 구분 — Claude가 문맥으로 추정)

## 전체 트랜스크립트
(Whisper 원문 그대로)
```

**Speaker Diarization:** Whisper는 화자 구분 미지원. Claude가 트랜스크립트 문맥으로 화자 추정.
- 단일 화자가 명확한 경우 발화 내용 섹션 생략
- 화자 구분이 불확실한 경우 "화자 구분 불가" 명시, 섹션 생략
- 향후 `pyannote-audio` 연동 확장 포인트 유지

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
| `output_language` | `auto` | ✅ (`auto`/`ko`/`en`) | 회의록 작성 언어 (`auto`=트랜스크립트 주 언어 사용) |
| `whisper_model` | `large` | ❌ 고정 | Whisper 모델 |

---

## 사전 설치 요구사항

| 의존성 | macOS | Windows |
|--------|-------|---------|
| Node.js 18+ | `brew install node` | winget/공식 사이트 |
| sox | `brew install sox` | `choco install sox` + lame codec 별도 설치 필요 |
| Python 3.9+ | 기본 설치 | [python.org/downloads](https://python.org/downloads) |
| faster-whisper | 플러그인 로드 시 자동 설치 | 플러그인 로드 시 자동 설치 |

**Windows sox 주의사항:** Chocolatey의 sox는 `rec` 바이너리가 누락되는 경우가 있음. [공식 sox 바이너리](https://sourceforge.net/projects/sox/files/sox/) 직접 설치를 권장. 설치 검증: `rec --version` 실행 확인.

**Whisper 모델 다운로드:** 최초 실행 시 `large-v3` 모델(약 3GB)이 `~/.cache/huggingface/`에 자동 다운로드됨. 초기 실행은 네트워크 환경에 따라 수 분 소요.

## 플러그인 설정 파일

### `.claude-plugin/plugin.json`
```json
{
  "name": "meeting-simplifier",
  "description": "회의 녹음 및 회의록 자동 생성",
  "version": "1.0.0",
  "author": { "name": "ain" }
}
```

### `.mcp.json`
```json
{
  "mcpServers": {
    "meeting-simplifier": {
      "command": "node",
      "args": ["mcp-server/index.js"],
      "env": {}
    }
  }
}
```

---

## 에러 처리

| 상황 | 처리 방식 |
|------|-----------|
| 마이크 접근 권한 없음 | 명확한 에러 메시지 + OS별 권한 설정 안내 |
| `sox`/`rec` 미설치 | 설치 방법 안내 메시지 |
| `faster-whisper` 미설치 | 설치 방법 안내 메시지 |
| 녹음 중 중단 (Ctrl+C 등) | 임시 파일 정리 후 종료 |
| 트랜스크립트 결과 빈 값 | "음성이 감지되지 않았습니다" 안내 |
| 파일 저장 권한 없음 | 대체 경로 제안 (바탕화면 등) |
| 긴 녹음 (1시간+) | 10분 청크 분할 처리, 각 청크 완료 시 진행 상황 보고 |
| 이미 녹음 중에 start 재호출 | "이미 녹음 중입니다" 에러 반환 |
| 녹음 없이 stop 호출 | "진행 중인 녹음이 없습니다" 에러 반환 |

---

## 지원 플랫폼

- macOS (Apple Silicon / Intel)
- Windows 10/11
