---
description: >
  회의 녹음을 중지하고 회의록을 생성합니다.
  트리거: "녹음 끝", "녹음 종료", "녹음 멈춰", "녹음 중지", "회의 끝났어", "미팅 종료",
  "회의 마칠게", "회의록 만들어줘", "회의록 정리해줘",
  "stop recording", "end meeting", "finish recording"
---

다음 순서로 진행하세요:

1. Bash 도구로 녹음을 중지합니다:
   ```bash
   bash ~/.claude/plugins/marketplaces/meeting-simplifier/scripts/stop_recording.sh
   ```
   - `"ok": false` → 에러 메시지를 사용자에게 전달하고 중단합니다.
   - `"ok": true` → "녹음 완료 — 녹음 시간: {duration_seconds}초"를 사용자에게 알립니다.
   - `audio_path` 값을 기억합니다.

2. Bash 도구로 settings.json을 읽습니다:
   ```bash
   cat ~/.claude/plugins/marketplaces/meeting-simplifier/settings.json 2>/dev/null || echo '{}'
   ```
   - `output_language` (없으면 `"auto"`), `output_format` (없으면 `"md"`), `output_dir` (없으면 `"~/Documents/meetings"`) 값을 기억합니다.

3. 사용자에게 "텍스트 변환 중..."을 알린 뒤, Bash 도구로 텍스트 변환합니다:
   ```bash
   bash ~/.claude/plugins/marketplaces/meeting-simplifier/scripts/transcribe.sh "<1단계 audio_path>"
   ```
   - `error` 키가 있으면 에러 메시지를 사용자에게 전달하고 중단합니다.
   - 완료 후 "변환 완료"를 사용자에게 알립니다.
   - `transcript`와 `language` 값을 기억합니다.

4. 트랜스크립트를 바탕으로 다음 항목을 분석합니다:
   - **회의 제목**: 내용을 보고 간결한 한국어 제목 생성 (예: "분기-마케팅-전략-회의")
   - **언어**: `output_language`가 `ko` → 한국어, `en` → 영어, `auto` → 트랜스크립트 주요 언어로 작성

5. 아래 형식으로 회의록 본문(마크다운)을 작성합니다:

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

6. Bash 도구로 회의록을 저장합니다:
   ```bash
   PLUGIN_DIR=~/.claude/plugins/marketplaces/meeting-simplifier
   MINUTES_FILE=$(mktemp /tmp/meeting-minutes-XXXX.md)
   cat > "$MINUTES_FILE" << 'MINUTES_EOF'
{회의록 내용}
MINUTES_EOF
   "$PLUGIN_DIR/.venv/bin/python" "$PLUGIN_DIR/scripts/save_meeting.py" \
     --title "{회의 제목}" \
     --minutes-file "$MINUTES_FILE" \
     --audio-path "{1단계 audio_path}" \
     --format "{output_format}" \
     --output-dir "{output_dir}"
   rm -f "$MINUTES_FILE"
   ```
   - `error` 키가 있으면 에러 메시지를 사용자에게 전달합니다.

7. 완료 후 사용자에게 알립니다:
   "회의록이 저장되었습니다: {saved_dir}"
