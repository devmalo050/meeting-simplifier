---
description: >
  기존 오디오 또는 텍스트 파일로 회의록을 생성합니다.
  트리거: "이 파일 회의록으로 정리해줘", "녹음 파일 분석해줘", "파일 첨부할게 회의록 만들어줘",
  "summarize this recording", "make minutes from this file"
---

`$ARGUMENTS`에 파일 경로가 제공된 경우 해당 경로를 사용합니다.
파일 경로가 없으면 사용자에게 파일 경로를 요청하세요.

파일 확장자에 따라 처리합니다:
- `.wav`, `.mp3`, `.m4a` → `meeting_transcribe` 도구로 먼저 변환 후, 결과의 `elapsed_seconds` 값을 사용해 "변환 완료 ({elapsed_seconds}초)"를 사용자에게 알린 뒤 진행
- `.txt`, `.md` → 파일 내용을 직접 트랜스크립트로 사용

이후 `/meeting-simplifier:stop` skill의 3~6번 단계와 동일하게 진행합니다.
(회의록 작성 → `meeting_save` 호출 → 완료 안내)

단, 텍스트 파일(.txt/.md) 입력의 경우 `meeting_transcribe`를 호출하지 않으므로 `output_language`를 알 수 없습니다.
이 경우 `meeting_save` 결과의 `output_language` 값을 회의록 언어 결정에 사용하세요.

단, `meeting_save`의 `audio_path`는 오디오 파일인 경우 해당 파일 경로,
텍스트 파일인 경우 빈 문자열("")을 전달합니다.

`format`과 `output_dir`은 생략 가능합니다 (서버가 settings.json에서 자동으로 읽음).
