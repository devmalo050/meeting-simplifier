---
description: >
  기존 오디오 또는 텍스트 파일로 회의록을 생성합니다.
  트리거: "이 파일 회의록으로 정리해줘", "녹음 파일 분석해줘", "파일 첨부할게 회의록 만들어줘",
  "summarize this recording", "make minutes from this file"
---

`$ARGUMENTS`에 파일 경로가 제공된 경우 해당 경로를 사용합니다.
파일 경로가 없으면 사용자에게 파일 경로를 요청하세요.

1. Bash 도구로 settings.json을 읽습니다:
   ```bash
   cat ~/.claude/plugins/marketplaces/meeting-simplifier/settings.json 2>/dev/null || echo '{}'
   ```
   - `output_language` (없으면 `"auto"`), `output_format` (없으면 `"md"`), `output_dir` (없으면 `"~/Documents/meetings"`) 값을 기억합니다.

2. 파일 확장자에 따라 처리합니다:

   **오디오 파일 (`.wav`, `.mp3`, `.m4a`):**
   사용자에게 "텍스트 변환 중..."을 알린 뒤 Bash 도구로 변환합니다:
   ```bash
   bash ~/.claude/plugins/marketplaces/meeting-simplifier/scripts/transcribe.sh "<file_path>"
   ```
   - `error` 키가 있으면 에러 메시지를 전달하고 중단합니다.
   - 완료 후 "변환 완료"를 알립니다.
   - `transcript`와 `language` 값을 기억합니다.

   **텍스트 파일 (`.txt`, `.md`):**
   ```bash
   cat "<file_path>"
   ```
   파일 내용을 트랜스크립트로 사용합니다.

이후 `/meeting-simplifier:stop` 커맨드의 4~7번 단계와 동일하게 진행합니다.
(회의록 작성 → save_meeting.py 호출 → 완료 안내)

단, `save_meeting.py`의 `--audio-path`는:
- 오디오 파일인 경우: 해당 파일 경로
- 텍스트 파일인 경우: 빈 문자열 (인수 생략)
