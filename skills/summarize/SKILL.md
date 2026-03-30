---
name: summarize
description: >
  기존 오디오 또는 텍스트 파일로 회의록을 생성합니다.
  트리거: "이 파일 회의록으로 정리해줘", "녹음 파일 분석해줘", "파일 첨부할게 회의록 만들어줘",
  "summarize this recording", "make minutes from this file"
---

`$ARGUMENTS`에 파일 경로가 제공된 경우 해당 경로를 사용합니다.
파일 경로가 없으면 사용자에게 파일 경로를 요청하세요.

파일 확장자에 따라 처리합니다:

**오디오 파일 (`.wav`, `.mp3`, `.m4a`):**

Bash 도구로 변환합니다:
```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/transcribe.sh" "<audio_path>"
```
- 호출 전 "텍스트 변환 중..."을 사용자에게 알립니다.
- `error` 키가 있으면 에러 메시지를 전달하고 중단합니다.
- 완료 후 "변환 완료"를 사용자에게 알립니다.
- `transcript`와 `language` 값을 기억합니다.

**텍스트 파일 (`.txt`, `.md`):**

파일 내용을 직접 트랜스크립트로 사용합니다:
```bash
cat "<file_path>"
```

이후 `/meeting-simplifier:stop` skill의 3~7번 단계와 동일하게 진행합니다.
(설정 읽기 → 회의록 작성 → save_meeting.py 호출 → 완료 안내)

단, `save_meeting.py`의 `--audio-path`는:
- 오디오 파일인 경우: 해당 파일 경로
- 텍스트 파일인 경우: 빈 문자열 (인수 생략)
