---
description: >
  회의 녹음을 중지하고 회의록을 생성합니다.
  트리거: "녹음 끝", "녹음 종료", "녹음 멈춰", "녹음 중지", "회의 끝났어", "미팅 종료",
  "회의 마칠게", "회의록 만들어줘", "회의록 정리해줘",
  "stop recording", "end meeting", "finish recording"
---

다음 순서로 진행하세요:

1. `meeting_record_stop` 도구를 호출하여 녹음을 중지합니다.
   - 에러 반환 시 사용자에게 알리고 중단합니다.
   - 결과의 `duration_seconds` 값을 사용해 사용자에게 알립니다: "녹음 시간: {duration_seconds}초"

2. `meeting_transcribe` 도구를 호출합니다. (`audio_path`는 이전 단계 결과 사용)
   - 변환 중임을 사용자에게 알립니다: "녹음을 텍스트로 변환 중입니다..."
   - 변환 완료 후 결과의 `elapsed_seconds` 값을 사용해 사용자에게 알립니다: "변환 완료 ({elapsed_seconds}초)"
   - 에러 반환 시 사용자에게 알리고 중단합니다.

3. 트랜스크립트를 바탕으로 다음 항목을 분석합니다:
   - **회의 제목**: 내용을 보고 간결한 한국어 제목 생성 (예: "분기-마케팅-전략-회의")
   - **언어**: `${CLAUDE_PLUGIN_ROOT}/settings.json`의 `meeting-simplifier.output_language` 값을 사용합니다. (ko이면 한국어, en이면 영어, 설정 없으면 트랜스크립트 주요 언어로 작성)

4. 아래 형식으로 회의록 본문(마크다운)을 작성합니다:

    # {회의 제목}

    **일시:** {현재 날짜 및 시간}
    **언어:** {한국어 / 영어}

    ---

    ## 요약
    (핵심 내용 간략히)

    ## 상세 내용
    (주제별로 논의된 내용 정리)

    ## 결정 사항
    - ...

    ## 액션 아이템
    - ...

    ## 발화 내용
    (화자 구분이 가능한 경우만 포함. 단일 화자이거나 구분 불가 시 이 섹션 생략)

    ## 전체 트랜스크립트
    {transcript}

5. `meeting_save` 도구를 호출합니다:
   - `title`: 생성한 회의 제목
   - `transcript`: Whisper 원문
   - `minutes`: 위에서 작성한 회의록 본문
   - `audio_path`: **1단계** `meeting_record_stop` 결과의 `audio_path` (절대 다른 값 사용 금지)
   - `format`: `${CLAUDE_PLUGIN_ROOT}/settings.json`의 `meeting-simplifier.output_format` 값 (없으면 "md")
   - `output_dir`: `${CLAUDE_PLUGIN_ROOT}/settings.json`의 `meeting-simplifier.output_dir` 값 (없으면 "~/Documents/meetings")

6. 완료 후 사용자에게 알립니다:
"회의록이 저장되었습니다: {saved_dir}"
