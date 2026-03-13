---
description: >
  meeting-simplifier 플러그인을 재설치합니다.
  트리거: "플러그인 재설치", "플러그인 업데이트", "reinstall plugin", "플러그인 다시 설치",
  "meeting-simplifier 재설치", "플러그인 새로고침"
---

다음 단계를 순서대로 실행하세요.

## 1단계: 캐시 삭제

Bash 도구로 아래 명령을 실행하세요:

```bash
rm -rf /Users/ain/.claude/plugins/cache/meeting-simplifier
```

## 2단계: 플러그인 제거

```bash
claude plugin uninstall meeting-simplifier 2>&1 || true
```

오류가 나도 계속 진행하세요.

## 3단계: 재설치

```bash
claude plugin install meeting-simplifier@meeting-simplifier 2>&1
```

## 4단계: 결과 확인

```bash
claude plugin list 2>&1 | grep -A4 "meeting-simplifier"
```

Status가 `✔ enabled`이면 성공입니다.
오류가 있으면 오류 메시지를 그대로 사용자에게 전달하세요.
