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
   DATA_DIR="${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}"
   PLUGIN_DIR="$(cat "$DATA_DIR/state/plugin_root" 2>/dev/null)"
   [ -z "$PLUGIN_DIR" ] && PLUGIN_DIR="$(ls -d ~/.claude/plugins/cache/*/meeting-simplifier/*/ 2>/dev/null | sort -V | tail -1)"
   [ -z "$PLUGIN_DIR" ] && PLUGIN_DIR=~/.claude/plugins/marketplaces/meeting-simplifier
   PLUGIN_DIR="${PLUGIN_DIR%/}"
   bash "$PLUGIN_DIR/scripts/stop_recording.sh"
   ```
   - `"ok": false` → 에러 메시지를 사용자에게 전달하고 중단합니다.
   - `"ok": true` → "녹음 완료 — 녹음 시간: {duration_seconds}초"를 사용자에게 알립니다.
   - `audio_path` 값을 기억합니다.

2. 사용자에게 "텍스트 변환 중..."을 알린 뒤, Bash 도구로 텍스트 변환합니다:
   ```bash
   DATA_DIR="${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}"
   PLUGIN_DIR="$(cat "$DATA_DIR/state/plugin_root" 2>/dev/null)"
   [ -z "$PLUGIN_DIR" ] && PLUGIN_DIR="$(ls -d ~/.claude/plugins/cache/*/meeting-simplifier/*/ 2>/dev/null | sort -V | tail -1)"
   [ -z "$PLUGIN_DIR" ] && PLUGIN_DIR=~/.claude/plugins/marketplaces/meeting-simplifier
   PLUGIN_DIR="${PLUGIN_DIR%/}"
   bash "$PLUGIN_DIR/scripts/transcribe.sh" "<1단계 audio_path>"
   ```
   - `error` 키가 있으면 에러 메시지를 사용자에게 전달하고 중단합니다.
   - `"status"`가 있고 `"ok": false`면, **직접 설치 명령을 만들지 말고** `message`를 사용자에게 그대로 전달하고 중단합니다. 단 `status`가 `python_missing`이면 "Python을 설치하겠습니다"라고 알린 뒤 아래 `install_python.sh`만 실행하고 그 결과 `message`를 그대로 전달합니다(installing/venv_pending/deps_failed는 message만 전달):
     ```bash
     bash "$PLUGIN_DIR/scripts/install_python.sh"
     ```
   - 완료 후 "변환 완료"를 사용자에게 알립니다.
   - `transcript`, `language`, `transcript_file` 값을 기억합니다.

3. 트랜스크립트를 바탕으로 다음 항목을 분석합니다:
   - **회의 제목**: 내용을 보고 간결한 한국어 제목 생성 (예: "분기-마케팅-전략-회의")
   - **언어**: 트랜스크립트의 주요 언어로 작성

4. 아래 형식으로 회의록 본문(마크다운)을 작성합니다.

   **작성 규칙 (반드시 준수):**
   - 음성에 실제로 언급된 내용만 작성합니다. 담당·기한·참석자·근거가 음성에 없으면 비우거나 "미정"으로 채우지 말고 **생략**합니다 (추측·추론 금지, 상세함보다 정확함 우선).
   - 내용이 없는 섹션은 통째로 생략합니다. 단 `한 줄 요약`·`핵심 포인트`·`논의 내용`은 항상 포함합니다.
   - 참석자는 화자 구분이 되지 않으므로, 음성에서 이름이 명시적으로 불린 경우에만 적습니다.
   - **"전체 트랜스크립트" 섹션은 저장 시 코드가 자동으로 붙이므로 본문에 직접 넣지 마세요** (길어도 잘리지 않게 하기 위함입니다).

    # {회의 제목}

    **일시:** {현재 날짜 및 시간}
    **녹음 길이:** {1단계 duration_seconds를 분·초로 환산, 예: 약 1분 56초}
    **참석자:** {음성에 이름이 언급된 경우만 — 아니면 이 줄 생략}
    **키워드:** {핵심 주제어 3~6개를 쉼표로}

    ---

    ## 한 줄 요약
    {회의 전체를 한 문장으로}

    ## 핵심 포인트
    - {3~5개 불릿}

    ## 논의 내용
    ### {안건/주제 1}
    - **논의:** {무엇을 이야기했나}
    - **의견/이견:** {다른 관점 — 있을 때만}
    - **결론:** {이 안건의 결론 — 있을 때만}
    ### {안건/주제 2}
    ...

    ## 결정 사항
    - {결정} — *근거:* {왜} ← 근거는 음성에 있을 때만. 결정이 없으면 섹션 생략

    ## 액션 아이템
    - [ ] {할 일} — 담당 {이름}/기한 {날짜} ← 담당·기한은 음성에 있을 때만. 액션이 없으면 섹션 생략

    ## 미결 사항
    {결론 나지 않은 쟁점 — 있을 때만 이 섹션 포함}

    ## 다음 단계
    {후속 일정·계획 — 있을 때만 이 섹션 포함}

5. Bash 도구로 회의록을 저장합니다:
   ```bash
   DATA_DIR="${MS_DATA_DIR:-$HOME/.claude/plugins/data/meeting-simplifier-meeting-simplifier}"
   PLUGIN_DIR="$(cat "$DATA_DIR/state/plugin_root" 2>/dev/null)"
   [ -z "$PLUGIN_DIR" ] && PLUGIN_DIR="$(ls -d ~/.claude/plugins/cache/*/meeting-simplifier/*/ 2>/dev/null | sort -V | tail -1)"
   [ -z "$PLUGIN_DIR" ] && PLUGIN_DIR=~/.claude/plugins/marketplaces/meeting-simplifier
   PLUGIN_DIR="${PLUGIN_DIR%/}"
   case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) VENV_PY="$DATA_DIR/.venv/Scripts/python.exe";; *) VENV_PY="$DATA_DIR/.venv/bin/python";; esac
   MINUTES_FILE=$(mktemp 2>/dev/null || echo "$DATA_DIR/state/minutes.md")
   cat > "$MINUTES_FILE" << 'MINUTES_EOF'
{회의록 내용}
MINUTES_EOF
   "$VENV_PY" "$PLUGIN_DIR/scripts/save_meeting.py" \
     --title "{회의 제목}" --minutes-file "$MINUTES_FILE" \
     --audio-path "{1단계 audio_path}" --transcript-file "{2단계 transcript_file}"
   rm -f "$MINUTES_FILE"
   ```
   - `error` 키가 있으면 에러 메시지를 사용자에게 전달합니다.

6. 완료 후 사용자에게 알립니다:
   - "회의록이 저장되었습니다: {saved_dir}"
   - 결과에 `"audio_moved": false`가 있으면, 녹음 파일이 원본 위치(`audio_source`)에 그대로 남아 있음을 함께 안내합니다.
