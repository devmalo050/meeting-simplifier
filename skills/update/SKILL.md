---
description: >
  meeting-simplifier 플러그인을 최신 버전으로 업데이트합니다.
  트리거: "플러그인 업데이트", "meeting-simplifier 업데이트", "update plugin", "플러그인 최신버전으로"
---

다음 단계를 순서대로 실행하세요.

## 1단계: 캐시 및 마켓플레이스 삭제

```bash
rm -rf /Users/ain/.claude/plugins/cache/meeting-simplifier
rm -rf /Users/ain/.claude/plugins/marketplaces/meeting-simplifier
```

## 2단계: 최신 버전 재설치

```bash
claude plugin install meeting-simplifier@meeting-simplifier --scope user 2>&1
```

## 3단계: 결과 확인

```bash
claude plugin list --json 2>&1 | python3 -c "import json,sys; [print('버전:', p['version'], '/ 상태:', '✔' if p['enabled'] else '✘') for p in json.load(sys.stdin) if 'meeting-simplifier' in p['id']]"
```

성공하면 사용자에게 알립니다: "meeting-simplifier가 최신 버전으로 업데이트되었습니다."
오류가 있으면 오류 메시지를 그대로 전달하세요.
