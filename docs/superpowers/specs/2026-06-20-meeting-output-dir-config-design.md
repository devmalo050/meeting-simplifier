# 회의록 저장 폴더 설정 — 설계 스펙
<!-- 작성: 2026-06-20 -->

## 배경

회의록(최종 `.md`)은 현재 `~/Documents/meetings/<날짜-시각-제목>/` 아래에 저장된다. 이 기본 경로는 `scripts/save_meeting.py`의 `--output-dir` argparse 기본값으로 **하드코딩**되어 있고, `commands/stop.md`·`commands/summarize.md`는 `save_meeting.py`를 호출할 때 `--output-dir`를 넘기지 않으므로 사용자는 저장 위치를 바꿀 방법이 없다.

작업 데이터(임시 오디오·Whisper 모델 캐시)는 `MS_DATA_DIR` 환경변수로 이미 변경 가능하지만, 이는 셸 프로파일을 편집해야 하는 개발자용 메커니즘이다.

## 목표

비개발자("일반인")가 **자연어로** 회의록 저장 폴더를 **바꾸고 / 확인하고 / 되돌릴** 수 있게 한다. 한 번 바꾸면 이후 모든 회의록에 **영구 적용**된다. 사용자는 터미널·환경변수·설정 파일을 직접 건드리지 않는다.

## 비목표 (YAGNI)

- 회의별 일회성 경로 지정(override) — 영구 기본값만 다룬다.
- 작업 데이터 디렉토리(`MS_DATA_DIR`) 변경 UI — 이미 환경변수로 가능하고 일반인 대상이 아니다.
- 프로젝트(cwd)별 설정 — 회의 녹음은 어느 폴더에서나 하므로 **글로벌 설정**만 둔다.
- 환경변수(`MS_OUTPUT_DIR`) 신설 — 영구화에 셸 프로파일 편집이 필요해 일반인 요구와 배치된다.

## 사용자 경험

자연어 트리거로 동작하는 단일 스킬(`meeting-simplifier:set-output-dir`).

- **변경**: "회의록 저장 위치 바꿔줘", "회의록 바탕화면에 저장해줘"
  → 위치를 경로로 해석 → 저장 직전 최종 경로를 사용자에게 확인 → config 기록 →
  "이제부터 회의록은 `~/Desktop/회의록`에 저장됩니다" 안내.
- **조회**: "회의록 지금 어디에 저장돼?"
  → 현재 설정값(없으면 기본값 `~/Documents/meetings`)을 안내.
- **리셋**: "회의록 저장 위치 원래대로 돌려줘"
  → config에서 `output_dir`를 제거(기본값으로 복귀) → 안내.

### 경로 해석 정책 (일반인 배려)

일반인은 절대경로를 모를 수 있으므로 커맨드(스킬)가:
1. "바탕화면 / 문서함 / 다운로드" 같은 표현을 OS 표준 폴더로 매핑한다(`~/Desktop`, `~/Documents`, `~/Downloads`).
2. 모호하면 사용자에게 되묻는다.
3. **저장 직전에 최종 절대경로를 사용자에게 보여주고 확인**받는다(엉뚱한 위치 방지).

## 아키텍처

| 파일 | 상태 | 역할 |
|---|---|---|
| `scripts/config.py` | 신규 | 설정 읽기/쓰기 단일 책임. `$MS_DATA_DIR/config.json`을 다룬다. CLI(조회/변경/리셋)와 import 양용. |
| `scripts/save_meeting.py` | 수정 | `--output-dir` 미지정 시 `config`에서 출력 디렉토리를 읽는다. |
| `commands/set-output-dir.md` | 신규 | 자연어 스킬. 위치 해석 → `config.py` CLI 호출 → 결과 안내. |

### `scripts/config.py`

- **데이터 디렉토리 결정**: `record.py`·`transcribe_server.py`·`lib_env.sh`와 동일한 규칙(`MS_DATA_DIR` 우선, 없으면 `~/.claude/plugins/data/meeting-simplifier-meeting-simplifier`)을 가벼운 자체 함수로 구현한다. 무거운 모듈(`record.py` 등)을 import하지 않는다.
- **config 경로**: `<data_dir>/config.json`.
- **함수**:
  - `get_output_dir() -> str | None` — config에 `output_dir`가 있으면 반환, 없으면 `None`.
  - `set_output_dir(path: str)` — 경로 검증 후 config에 기록.
  - `unset_output_dir()` — config에서 `output_dir` 키 제거.
- **CLI**(스킬이 호출): `--show`(현재 유효 경로 JSON 출력) / `--set <path>` / `--reset`. 모든 결과는 JSON으로 stdout 출력(커맨드가 파싱), 기존 스크립트 관례와 일치.
- **검증**: `--set` 시 `expanduser`로 확장한 경로의 디렉토리를 생성 가능한지(쓰기 권한) 확인한다. 불가하면 config를 바꾸지 않고 `{"ok": false, "message": "..."}` 반환.

### `scripts/save_meeting.py` 수정

`main()`에서 출력 디렉토리 결정 우선순위를 다음으로 둔다:

```
명시적 --output-dir 인자 > config.get_output_dir() > 기본값 "~/Documents/meetings"
```

- argparse 기본값을 `None`(sentinel)로 바꾸고, `None`일 때만 config → 기본값 순으로 폴백한다.
- `commands/stop.md`·`summarize.md`는 현재도 `--output-dir`를 넘기지 않으므로 **수정 불필요**(변경 범위 최소화).
- `save_meeting()`의 기존 `PermissionError → ~/Desktop` 폴백은 그대로 유지한다.

### `commands/set-output-dir.md`

- 프런트매터 `description`에 한국어/영어 트리거를 나열(다른 커맨드와 동일한 스타일).
- 본문은 결정론적 절차: PLUGIN_DIR·DATA_DIR 유도(기존 커맨드와 동일 패턴) → 위치 해석/확인 → `config.py` CLI(`--set`/`--show`/`--reset`) 호출 → JSON 결과의 `ok`/`message`를 사용자에게 전달.
- 임의로 파일을 직접 쓰지 말고 `config.py`만 호출하도록 명문화(로직 캡슐화, LLM 자유도 축소 — 기존 `install_python.sh` 패턴과 동일 철학).

## 데이터 흐름

```
[변경]  사용자 자연어
          → set-output-dir.md (위치 해석 + 확인)
          → config.py --set <abs_path>
          → config.json: {"output_dir": "<abs_path>"}

[사용]  stop.md / summarize.md (--output-dir 안 넘김)
          → save_meeting.py
          → config.get_output_dir()  (없으면 ~/Documents/meetings)
          → 회의록 저장
```

## config.json 형식

```json
{ "output_dir": "/Users/me/Desktop/회의록" }
```

단일 키로 시작하되, 향후 `WHISPER_MODEL` 등 다른 런타임 설정을 흡수할 수 있는 객체 구조를 유지한다. 알 수 없는 키는 보존한다(전방 호환).

## 에러 처리

- **config.json 파손/부재**: 읽기 시 예외를 삼키고 "설정 없음"으로 간주(기본값 사용). 회의록 저장이 설정 오류로 실패하지 않게 한다.
- **`--set` 경로 쓰기 불가**: config를 바꾸지 않고 실패 메시지 반환. 잘못된 설정이 다음 회의록을 유실시키는 것을 막는다.
- **저장 시 권한 오류**: `save_meeting.py`의 기존 `~/Desktop` 폴백 유지.

## 테스트 전략

`pytest`, 기존 `MS_DATA_DIR` 격리 픽스처(`tests/conftest.py`) 재사용.

- `config.py`: set→get 왕복, unset 후 `None`, 잘못된 경로 거부, 파손 JSON 시 안전 폴백.
- `save_meeting.py` 우선순위: ① 명시 인자가 config·기본값을 이긴다, ② 인자 없고 config 있으면 config 사용, ③ 둘 다 없으면 `~/Documents/meetings`.

## 결정과 이유

- **설정을 `save_meeting.py`에서 읽기**(커맨드 인자 전파 아님): `stop`/`summarize`가 이미 `--output-dir`를 안 넘기므로, 읽기 지점을 `save_meeting.py`에 두면 커맨드 수정이 불필요하고 단일 진입점에 일관된다.
- **데이터 폴더 내 `config.json`**(프로젝트별/.local.md 아님): 회의 녹음은 어느 폴더에서나 하므로 글로벌이어야 하고, `MS_DATA_DIR` 경로 로직이 이미 셸·파이썬에 일관돼 결합이 깔끔하다.
- **스킬(자연어) + 설정 파일 조합**: 스킬은 호출 UX, 파일은 영속성. 스킬만으로는 값이 다음 세션에 유지되지 않는다.
- **로직을 `config.py`에 캡슐화하고 커맨드는 호출만**: LLM이 임의로 파일을 쓰는 자유도를 없애 결정론을 확보(기존 `install_python.sh` 패턴 답습).

## 영향 받는 파일

- 신규: `scripts/config.py`, `commands/set-output-dir.md`, `tests/test_config.py`, `tests/test_save_meeting.py`(우선순위 케이스)
- 수정: `scripts/save_meeting.py`
- 버전: `.claude-plugin/plugin.json`·`marketplace.json` 1.5.1 → 1.6.0(기능 추가)
- 문서: `README.md`(저장 폴더 변경 안내 섹션)
