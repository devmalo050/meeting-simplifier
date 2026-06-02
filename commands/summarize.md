---
description: >
  기존 오디오 또는 텍스트 파일로 회의록을 생성합니다.
  트리거: "이 파일 회의록으로 정리해줘", "녹음 파일 분석해줘", "파일 첨부할게 회의록 만들어줘",
  "summarize this recording", "make minutes from this file"
---

`$ARGUMENTS`에 파일 경로가 제공된 경우 해당 경로를 사용합니다.
파일 경로가 없으면 사용자에게 파일 경로를 요청하세요.

파일 확장자에 따라 처리합니다:

**오디오 파일 (`.wav`, `.mp3`, `.m4a`):**
사용자에게 "텍스트 변환 중..."을 알린 뒤 Bash 도구로 변환합니다:
```bash
PLUGIN_DIR=$(ls -d ~/.claude/plugins/cache/*/meeting-simplifier/*/ 2>/dev/null | sort -V | tail -1)
[ -z "$PLUGIN_DIR" ] && PLUGIN_DIR=~/.claude/plugins/marketplaces/meeting-simplifier
PLUGIN_DIR="${PLUGIN_DIR%/}"
bash "$PLUGIN_DIR/scripts/transcribe.sh" "<file_path>"
```
- `error` 키가 있으면 에러 메시지를 전달하고 중단합니다.
- 완료 후 "변환 완료"를 알립니다.
- `transcript`, `language`, `transcript_file` 값을 기억합니다.

**텍스트 파일 (`.txt`, `.md`):**
```bash
cat "<file_path>"
```
파일 내용을 트랜스크립트로 사용합니다. 이 경우 트랜스크립트 파일은 원본 `<file_path>` 자체입니다.

이후 `/meeting-simplifier:stop` 커맨드의 3~6번 단계와 동일하게 진행합니다.
(회의록 작성 → save_meeting.py 호출 → 완료 안내)

단, `save_meeting.py`의 인자는:
- `--audio-path`: 오디오 파일이면 해당 파일 경로, 텍스트 파일이면 생략
- `--transcript-file`: 오디오 파일이면 변환 결과의 `transcript_file`, 텍스트 파일이면 원본 파일 경로(`<file_path>`)

또한 회의록 본문의 `**녹음 길이:**` 줄은 `summarize` 경로에서는 길이를 알 수 없으므로 생략합니다.
