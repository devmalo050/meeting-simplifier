# HANDOFF — 저장 폴더 설정 + 품질 개선 배치 (main 1.7.1 배포 완료)
<!-- 작성: 2026-06-21 -->

## 🔥 핫 스테이트 (여기만 읽어도 재개 가능)
- **목표**: meeting-simplifier 플러그인에 (1) 회의록 저장 폴더를 일반인이 자연어로 바꾸는 기능, (2) 코드 품질 개선(테스트 갭·견고성·DRY·보안)을 더한다. **둘 다 완료·배포됨.**
- **현재 상태**: `main` 브랜치, 작업트리 clean, `origin/main`과 동기화. 버전 **1.7.1**(plugin.json + marketplace.json). 전체 테스트 **91 passed**. 직전 핸드오프(feat/onboarding-python, 1.5.0) 이후 이번 세션에서 **1.5.1 → 1.6.0 → 1.6.1 → 1.7.0 → 1.7.1**까지 5회 배포했고 전부 main 머지+push 끝남. 진행 중이던 개발 브랜치 없음.
- **바로 다음 할 일**:
  1. **사용자 환경 플러그인 갱신**(1.7.1 적용): `claude plugin marketplace update meeting-simplifier && claude plugin update meeting-simplifier@meeting-simplifier` → **새 세션**에서 적용. (직전 세션 사용자 정식 설치는 1.5.0이었으니, 한 번 갱신하면 1.7.1로 점프)
  2. **후속 polish chip 2건**(별도 워크트리/세션에서 진행 중일 수 있음, 머지 차단 아니었던 항목): ① config 빈 문자열 입력 통일(set_output_dir에 ValueError + main의 `elif args.set is not None`) + ② `commands/set-output-dir.md`의 `--reset`/`--show` 분기에도 ok:false 처리(--set과 대칭). 이건 사용자가 chip을 이미 **시작**(task_92dc3e8b)했으므로 다른 세션이 처리 중. 중복 착수 주의.
  3. **Windows 실기 검증**(이전부터 사용자 몫): Python 없는 새 Windows PC에서 온보딩 + 저장 폴더(바탕화면) + 녹음/회의록 end-to-end.
- **블로커**: 없음.

## 변경 사항 (이번 세션) — 모두 main에 머지·push 완료
### 신규 파일
- `scripts/config.py` — 플러그인 런타임 설정(`$MS_DATA_DIR/config.json`) 읽기/쓰기 + `--show`/`--set`/`--reset` CLI. `default_output_dir()`이 OS 분기(Windows `~/Desktop/meetings`, 그 외 `~/Documents/meetings`). 알 수 없는 키 보존, 파손 JSON 안전 폴백.
- `commands/set-output-dir.md` — 자연어 스킬 `meeting-simplifier:set-output-dir`. 저장 폴더 변경/조회/초기화. config.py CLI만 호출(직접 편집 금지), 경로 해석·저장직전 확인.
- `scripts/paths.py` — `is_windows`/`data_dir`/`state_dir`/`venv_python` 단일 진실원천(표준 라이브러리만, 무거운 import 없음).
- `tests/test_config.py`, `tests/test_save_meeting.py`, `tests/test_transcribe_server.py`, `tests/test_paths.py` — 신규/대폭 보강(전체 47→91).
- `docs/superpowers/specs/2026-06-20-meeting-output-dir-config-design.md`, `docs/superpowers/plans/2026-06-20-output-dir-config.md`, `docs/superpowers/plans/2026-06-20-quality-improvements.md` — 설계/플랜.
### 수정 파일
- `scripts/save_meeting.py` — `--output-dir` 미지정 시 config 사용(`resolve_output_dir`, 인자>설정>기본값) + 공백 제목 방어(main의 `title.strip()`).
- `scripts/record.py` — json.loads 크래시 방어(cmd_start/stop), spawn_worker log FD close, `wav_duration`을 공개 `getnframes()`로(private 의존 제거). data/venv 경로는 `from paths import …`로 위임.
- `scripts/transcribe_server.py` — `_data_chunk_offset()` 신규(raw RIFF data 오프셋), `read_wav_duration`·`fix_wav_header` 둘 다 이걸로 LIST청크 대응. `transcript_out_dir`이 paths 위임. NamedTemporaryFile `tmp.close()` 추가.
- `scripts/setup.sh` — WHISPER_MODEL을 `python3 -c` 문자열 치환 → `sys.argv` 전달(코드 주입 방어).
- `scripts/stop_recording.sh` — `lib_env.sh` source로 data_dir/venv_python 중복 제거(start_recording.sh와 일관).
- `commands/stop.md`, `commands/summarize.md` — "회의록 정리해줘" 트리거 겹침 해소(summarize는 파일 맥락 명시) + summarize 입력 안내.
- `README.md` — 저장 폴더 변경 안내, 플랫폼별 기본 경로(macOS Documents / Windows Desktop), Git for Windows 설치 안내, 슬래시 통일.
- `.claude-plugin/plugin.json` / `marketplace.json` — 1.5.1 → 1.7.1 (단계적).

## 결정과 이유
- **저장 경로 = 자연어 스킬(입구) + config.json(기억)** — 일반인이 환경변수/설정파일을 직접 안 건드리게. 기각: 환경변수 신설(영구화에 셸 프로파일 편집 필요), 프로젝트별 `.local.md`(글로벌 도구라 어느 폴더서 녹음하든 동일해야 함).
- **설정 읽기를 save_meeting.py에서** — stop/summarize가 이미 `--output-dir`를 안 넘기므로 커맨드 수정 불필요.
- **Windows 기본 = `~/Desktop/meetings`(하위폴더)** — 회의록이 `<날짜-시각-제목>/` 폴더 단위라 바탕화면 직접은 어수선. macOS는 기존 `~/Documents/meetings` 유지.
- **config.py가 record.py를 import 안 함** — record.py는 sounddevice 등 무거운 의존성. 그래서 data_dir 로직을 가벼운 `paths.py`로 공통화(record/config/transcribe 모두 import).
- **품질배치: 테스트 먼저, DRY 리팩토링 나중** — 테스트 안전망이 paths.py 리팩토링 회귀를 잡게.
- **wav_duration(record.py)은 `getnframes()`, read_wav_duration(transcribe)은 파일크기 기반** — record는 자기가 쓴 정상 WAV(헤더 정확), transcribe는 외부 node-record-lpcm16 파일(헤더 data chunksize 부정확)이라 파일 크기로 계산해야 함. 비대칭은 의도적.

## 막다른 길 / 실패한 시도
- **세션 리밋(3am Asia/Seoul 리셋)으로 품질배치 Task 3 implementer가 0토큰에서 중단** → 리밋 해제 후 작업트리 clean·ledger 미완 확인하고 같은 base에서 재dispatch해 성공. 교훈: SDD ledger(`.superpowers/sdd/progress.md`)와 git log로 재개 지점을 신뢰.
- **`wave.rewind(); wave.tell()`이 바이트 오프셋이 아니라 프레임 위치(rewind 후 0)** — 플랜 brief가 "rewind/tell로 data offset 구하라"고 제안했으나 실제로는 항상 0. `fix_wav_header`와 `wav_duration`/`read_wav_duration` 세 곳에 같은 함정이 있었음. 해결: record.py는 `getnframes()`(공개 API), transcribe_server는 `_data_chunk_offset()`(raw RIFF로 'data' 청크 시작 직접 파싱, data 크기 필드는 node 버그로 부정확하니 무시하고 파일 크기 사용). LIST 청크 있는 WAV에서 검증.
- (서브에이전트 리뷰가 잡은 것) save_meeting 테스트의 `monkeypatch` 후 `importlib.reload` 패턴이 비결정적(reload 중 fake 소비) → reload 제거하고 `save_mod.shutil`/`save_mod.os`에 직접 monkeypatch로 수정.

## 원시 데이터 (그대로)
- 최종 테스트: `.venv/bin/python -m pytest tests/ -q` → **91 passed**. (config 11 + save_meeting 21 + transcribe_server 16 + paths 5 + record 등)
- 버전: `plugin.json 1.7.1 / marketplace.json 1.7.1 / MATCH`.
- 이번 세션 main 커밋(최신순 일부): `ca2d914`(fix_wav_header) `5927b62`(read_wav_duration) `add1edb`(1.7.0 문서/보안) `9981a03`(paths.py) `a432b83`(wav_duration getnframes) `b1c3d15`(record json/FD) `cf04bae`(transcribe 테스트) `e2e78f8`(Windows 바탕화면) … 그 전 1.6.0/1.5.1.
- 발견·수정한 실제 버그: save_meeting 공백 제목 → trailing-dash 디렉토리(`2026-06-20-235308--`). fix_wav_header가 LIST청크 WAV에서 거짓 `was_fixed=True`.
- 셸 문법: `bash -n scripts/*.sh` → OK.

## 열린 스레드 / 블로커
- 후속 polish chip 2건(머지 차단 아님): config 빈 문자열 통일 + set-output-dir.md 조회/초기화 ok:false 대칭. `task_92dc3e8b`로 사용자가 **이미 시작**(별도 세션 진행 중일 수 있음 — 중복 착수 금지). 작업 시 버전은 현재(1.7.1)에서 patch +1.
- Windows 실기 검증 미완(사용자 몫): 온보딩(Python 자동설치, UAC, 세션 재시작) + 저장 폴더(바탕화면 기본) + 녹음 e2e.

## 다음 단계 (순서대로)
1. 사용자 플러그인 갱신(1.7.1): `claude plugin marketplace update meeting-simplifier && claude plugin update meeting-simplifier@meeting-simplifier` → 새 세션 적용.
2. 후속 polish chip(빈 문자열 + ok:false 대칭) 상태 확인 — 이미 진행 중이면 결과만 확인, 미진행이면 feat 브랜치 새로 파서 TDD로(set_output_dir ValueError + main `is not None`, 커맨드 3분기 대칭), 버전 1.7.2.
3. (사용자) Windows 실기 검증. 실패 항목은 해당 스크립트/커맨드로 회귀 수정 후 patch 올림.

## 핵심 파일 / 위치
- `scripts/config.py` — `default_output_dir()`(OS 분기), `get/set/unset_output_dir`, `effective_output_dir`, `--show/--set/--reset` CLI.
- `scripts/paths.py` — data/venv 경로 단일 진실원천(record/config/transcribe가 import).
- `scripts/transcribe_server.py:15` 부근 — `_data_chunk_offset()`(LIST청크 대응 raw RIFF 파싱), `read_wav_duration`·`fix_wav_header`가 사용.
- `scripts/save_meeting.py` — `resolve_output_dir`(인자>설정>기본값), 공백 제목 방어.
- `commands/set-output-dir.md` — 자연어 저장폴더 스킬(config.py CLI만 호출).

## 실행 / 테스트
- 테스트: `.venv/bin/python -m pytest tests/ -q` (루트에서).
- 셸 문법: `bash -n scripts/*.sh`.
- config CLI 수동: `MS_DATA_DIR=/tmp/x .venv/bin/python scripts/config.py --show` (→ `--set <경로>` → `--reset`).
- 로컬 브랜치 플러그인 시험(머지 없이): `claude --plugin-dir /Users/ain/Projects/meeting-simplifier` (해당 브랜치 체크아웃 상태에서).

## 참조 (복제 금지, 경로/URL만)
- 저장폴더 설계 스펙: `docs/superpowers/specs/2026-06-20-meeting-output-dir-config-design.md`
- 저장폴더 구현 플랜: `docs/superpowers/plans/2026-06-20-output-dir-config.md`
- 품질개선 구현 플랜(5태스크): `docs/superpowers/plans/2026-06-20-quality-improvements.md`
- SDD 진행 ledger(git-ignored): `.superpowers/sdd/progress.md`
- 직전 작업(Windows Python 자동설치): `git show HEAD~N:HANDOFF.md`는 1db2e2b 이전 커밋의 HANDOFF, 또는 `docs/superpowers/plans/2026-06-20-onboarding-python.md`
- 저장소: github.com/devmalo050/meeting-simplifier (main = 1.7.1 배포됨)
