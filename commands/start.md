---
description: >
  회의 녹음을 시작합니다.
  트리거: "회의 녹음 시작해줘", "녹음 시작", "녹음해줘", "회의 시작할게", "미팅 시작해",
  "회의 시작", "지금부터 회의 녹음", "회의 들어갈게",
  "record meeting", "start recording", "start meeting"
---

Bash 도구로 다음을 실행하세요:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/start_recording.sh"
```

결과 JSON을 파싱합니다:
- `"ok": true` → "녹음을 시작했습니다. 회의가 끝나면 '녹음 끝' 또는 '회의록 만들어줘' 라고 말씀해주세요."
- `"ok": false` → `error` 값을 사용자에게 전달하세요.
