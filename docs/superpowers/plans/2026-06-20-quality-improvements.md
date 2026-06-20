# 품질 개선 배치 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 개선점 스캔(adversarial 검증 통과 34건)을 파일/영역별로 묶어 구현한다 — 테스트 갭 메우기, 견고성, DRY 공통화, 문서/UX/보안.

**Architecture:** 파일 단위로 (테스트 추가 + 견고성 수정)을 묶어 충돌을 막는다. DRY 리팩토링(`paths.py`)은 테스트 안전망이 갖춰진 뒤(Task 4)에 수행해 회귀를 잡는다.

**Tech Stack:** Python 3 표준 라이브러리 + pytest, Bash 스크립트, Claude Code 커맨드(.md).

## Global Constraints

- 외부 의존성 추가 금지 — 표준 라이브러리만. (테스트에서 python-docx/faster-whisper/sounddevice/psutil 등 무거운/선택적 의존성은 monkeypatch·mock로 대체)
- 데이터 디렉토리 규칙: `MS_DATA_DIR` 우선, 없으면 `~/.claude/plugins/data/meeting-simplifier-meeting-simplifier`.
- 기존 테스트 패턴 준수: `tests/conftest.py`의 `MS_DATA_DIR` monkeypatch 픽스처 + `import <module>; importlib.reload(<module>)`.
- 회의록 기본 경로: macOS `~/Documents/meetings`, Windows `~/Desktop/meetings`(`config.default_output_dir()`).
- 주석은 "왜"가 비자명할 때만. UTF-8 BOM 없음.
- 버전 bump 시 `plugin.json` + `marketplace.json` 둘 다. 이 배치 완료 시 1.6.1 → 1.7.0(개선 묶음).
- 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- 각 태스크는 TDD. 견고성 수정은 RED(실패 테스트)→GREEN. 순수 테스트 추가는 기존 동작을 검증(추가 후 통과 확인).

---

### Task 1: save_meeting.py — 테스트 보강 + 빈/공백 제목 방어

**Files:**
- Modify: `scripts/save_meeting.py`
- Test: `tests/test_save_meeting.py`

**처리할 검증 항목:**
- 빈/공백 제목 → trailing-dash 디렉토리명(견고성, low). `main()`에서 `args.title.strip()`이 비면 `{"error": "..."}` 출력 후 비0 종료.
- `sanitize_dir_name()` 미테스트 → 특수문자 제거/공백→하이픈/80자 절삭 각 1케이스.
- `save_meeting()` 직접 호출 테스트 0건 → 아래를 `tmp_path` 기반으로 추가:
  - `fmt='md'`, `fmt='txt'` 각각 저장 후 파일 존재·내용·이름(`{safe_title}.{fmt}`) 검증.
  - `transcript_file` 있음/없음 → "전체 트랜스크립트" 섹션 병합([save_meeting.py:44-48](scripts/save_meeting.py:44)) 검증.
  - `audio_path` 지정 시 `shutil.move` 성공(audio_moved=True) + 실패(monkeypatch로 예외 → audio_moved=False, audio_error 포함) 검증.
  - PermissionError 폴백([save_meeting.py:58-63](scripts/save_meeting.py:58)): `os.makedirs` 첫 호출에서 PermissionError monkeypatch → `saved_dir`가 `~/Desktop` 아래인지.
  - `fmt='docx'`: `python-docx`를 monkeypatch로 ImportError 유발 → RuntimeError, 그리고 docx 모듈을 가짜로 주입해 헤딩 파싱 1케이스(가능하면). docx 라이브러리가 설치돼 있으면 실제 저장 1케이스.

**TDD 절차:**
- [ ] **Step 1:** 빈/공백 제목 방어 — 실패 테스트(공백 title로 `main` 또는 저장 호출 시 에러) 작성 → RED → `save_meeting.py main()`에 `title = args.title.strip()` 검증 추가 → GREEN.
- [ ] **Step 2:** `sanitize_dir_name` 단위 테스트 3케이스 추가 → 통과 확인.
- [ ] **Step 3:** `save_meeting()` 직접 호출 테스트(md/txt/transcript/audio move 성공·실패/PermissionError 폴백) 추가 → 통과 확인. 기존 동작 검증이므로 GREEN이어야 하며, 빨강이면 실제 버그를 발견한 것이니 보고.
- [ ] **Step 4:** docx 경로 테스트(ImportError→RuntimeError 최소 1케이스) 추가 → 통과.
- [ ] **Step 5:** `.venv/bin/python -m pytest tests/test_save_meeting.py -q` 전체 통과.
- [ ] **Step 6:** 커밋 `test+fix: save_meeting 저장 경로 테스트 보강 + 공백 제목 방어`.

---

### Task 2: transcribe_server.py — 테스트 보강 + 임시파일 close

**Files:**
- Modify: `scripts/transcribe_server.py`
- Test: `tests/test_transcribe_paths.py` (또는 신규 `tests/test_transcribe_server.py`)

**처리할 검증 항목:**
- `NamedTemporaryFile` close 누락(견고성, low): `fix_wav_header`([transcribe_server.py:63](scripts/transcribe_server.py:63))·`split_wav`([transcribe_server.py:84](scripts/transcribe_server.py:84))에서 `wave.open(...)` with 블록 종료 직후 `tmp.close()`(FD 해제, `delete=False`라 파일 유지).
- `read_wav_duration` 미테스트 → `record.py` 테스트의 WAV 생성 패턴으로 정상 WAV(예상 길이)·없는 파일(0) 2케이스.
- `fix_wav_header` 미테스트 → 정상 헤더(was_fixed=False, 원본 경로)·헤더 불일치(was_fixed=True, tmp 생성)·예외(원본 반환) 케이스.
- `split_wav` 미테스트 → 짧은 WAV(1청크)·`CHUNK_SECS` 초과 WAV(다수 청크), 청크 수·각 청크 존재 검증. (테스트에서는 `CHUNK_SECS`를 작게 monkeypatch해 긴 오디오를 흉내)
- `_transcribe` 미테스트 → `WhisperModel`을 가짜 객체(segments/info를 돌려주는 mock)로 주입해 단일 경로·긴 오디오 청크 경로·청크 도중 예외 시 정리([transcribe_server.py:125-129](scripts/transcribe_server.py:125)) 검증. `language` 파라미터(None/'auto'→None) 1케이스.

**주의:** `from faster_whisper import WhisperModel`이 모듈 import 시 실행된다. 테스트는 `sys.modules`에 가짜 `faster_whisper`를 주입한 뒤 import하거나, 함수에 model을 인자로 넘기는 `transcribe`/`_transcribe`를 직접 호출(model mock)하는 방식으로 무거운 의존성을 회피한다.

**TDD 절차:**
- [ ] **Step 1:** 임시파일 close — `fix_wav_header`/`split_wav`에 `tmp.close()` 추가. (FD 누수는 직접 단언이 어려우므로, 동작 보존을 회귀 테스트로 확인: 헤더 수정/청킹 결과가 동일한지)
- [ ] **Step 2:** `read_wav_duration` 테스트 2케이스 → 통과.
- [ ] **Step 3:** `fix_wav_header` 테스트(정상/불일치/예외) → 통과.
- [ ] **Step 4:** `split_wav` 테스트(`CHUNK_SECS` monkeypatch로 1청크/다청크) → 통과.
- [ ] **Step 5:** `_transcribe` 테스트(model mock, 단일/청크/예외정리/language) → 통과.
- [ ] **Step 6:** `.venv/bin/python -m pytest tests/ -q` 전체 통과.
- [ ] **Step 7:** 커밋 `test+fix: transcribe_server 핵심 로직 테스트 + 임시파일 close`.

---

### Task 3: record.py — 테스트 보강 + json.loads 방어 + log FD close + wav_duration 정확화

**Files:**
- Modify: `scripts/record.py`
- Test: `tests/test_record.py`

**처리할 검증 항목:**
- `json.loads` 크래시 방어(견고성, medium): [record.py:172](scripts/record.py:172)·[record.py:241](scripts/record.py:241)을 `try/except json.JSONDecodeError`로 감싸 손상 시 `{"ok": False, "error": "상태 파일이 손상되었습니다"}` 반환(스택트레이스 대신).
- `spawn_worker` log FD close(견고성, low): [record.py:142-145](scripts/record.py:142) `Popen` 직후 `log.close()`.
- `wav_duration` 44바이트 하드코딩(견고성, low): [record.py:82](scripts/record.py:82)를 `transcribe_server.fix_wav_header`처럼 `wave`의 `rewind()/tell()`로 data offset을 구해 계산(LIST 청크 대응). `read_wav_duration`/`wav_duration` 로직이 유사하므로 동일 방식으로 정렬.
- `force_kill` 미테스트(low) → psutil mock·`os.kill` mock으로 정상/폴백 경로.
- `main()` dispatch 미테스트(low) → `main([])`(command required)·`main(['badcmd'])`(unknown command) 2케이스, stdout JSON 확인.

**TDD 절차:**
- [ ] **Step 1:** json.loads 방어 — 손상된 `result.json`을 둔 상태에서 `cmd_start`/`cmd_stop`이 크래시 대신 에러 dict 반환하는 실패 테스트 → RED → try/except 추가 → GREEN.
- [ ] **Step 2:** `wav_duration` — LIST 청크가 있는(44바이트 초과 헤더) WAV에서 정확한 길이를 내는 테스트 → 필요 시 RED → rewind/tell 구현 → GREEN. (단순 정상 WAV는 기존 계산과 동일)
- [ ] **Step 3:** `spawn_worker` log FD close 추가. (회귀: 녹음 시작이 여전히 동작; 직접 단언이 어려우면 close 호출을 monkeypatch로 확인)
- [ ] **Step 4:** `force_kill`·`main` dispatch 테스트 추가 → 통과.
- [ ] **Step 5:** `.venv/bin/python -m pytest tests/ -q` 전체 통과.
- [ ] **Step 6:** 커밋 `test+fix: record.py json 방어·FD close·wav_duration 정확화 + 테스트`.

---

### Task 4: DRY — scripts/paths.py 공통 모듈 + 셸 source 정리

**Files:**
- Create: `scripts/paths.py`
- Modify: `scripts/record.py`, `scripts/config.py`, `scripts/transcribe_server.py`, `scripts/stop_recording.sh`, `scripts/setup.sh`
- Test: `tests/test_paths.py` (신규), 기존 테스트 조정

**처리할 검증 항목:**
- `data_dir()`가 record.py/config.py/transcribe_server.py에 중복(medium). `venv_python` 분기·기본값 문자열 중복(low).
- 셸: `stop_recording.sh`가 `lib_env.sh`를 source 안 하고 `data_dir`/`venv_python` 재구현(low). `start_recording.sh`는 이미 source함.

**설계:**
- `scripts/paths.py` (표준 라이브러리만, 무거운 import 없음): `is_windows()`, `data_dir()`, `state_dir()`, `venv_python(dd=None)`, `DEFAULT_DATA_SUBPATH`.
- `record.py`: 자체 정의 4함수를 `from paths import is_windows, data_dir, state_dir, venv_python`로 대체(이름이 모듈에 그대로 노출되어 기존 `record_mod.data_dir()` 접근 유지).
- **주의(테스트 monkeypatch 대상 이동):** `test_record.py`의 `test_venv_python_posix/windows`는 `record_mod.is_windows`를 monkeypatch하는데, `venv_python`이 `paths`로 옮겨가면 `paths.is_windows`를 참조하므로 패치가 안 먹는다. → 이 두 테스트를 `tests/test_paths.py`로 옮기고 `paths.is_windows`를 monkeypatch하도록 변경. `record.py`는 import만.
- `config.py`: `data_dir`/`config_path`는 `paths.data_dir` 사용(단 `config.py`는 `set_output_dir` 등 자체 책임 유지; `default_output_dir`는 그대로).
- `transcribe_server.py`: `transcript_out_dir()`이 `paths.state_dir()`를 사용(현 `os.path.join` 스타일 → paths 위임).
- `stop_recording.sh`: 상단에서 `lib_env.sh`를 source 후 `ms_data_dir`/`ms_venv_python` 사용(start_recording.sh와 동일 패턴). `setup.sh`도 가능하면 `lib_env.sh` source로 기본값 중복 제거(단 setup은 lib_env보다 먼저 실행될 수 있으니 경로 의존성 확인 후 안전하면 적용, 아니면 보류하고 보고).
- `record.py`의 `venv_python`은 현재 record 내부에서 미사용이나 paths로 이전해 셸/테스트 공유.

**TDD 절차:**
- [ ] **Step 1:** `tests/test_paths.py` 작성(data_dir env/기본값, state_dir 생성, venv_python posix/windows) → RED(paths 없음).
- [ ] **Step 2:** `scripts/paths.py` 구현 → test_paths 통과.
- [ ] **Step 3:** `record.py`/`config.py`/`transcribe_server.py`가 paths를 import하도록 수정. `test_record.py`의 venv_python 2테스트를 test_paths로 이전. 전체 `pytest tests/ -q` 통과(회귀 확인).
- [ ] **Step 4:** `stop_recording.sh`가 `lib_env.sh` source하도록 수정. `bash -n` 문법 확인 + `bash scripts/lib_env.sh status` 동작 확인.
- [ ] **Step 5:** setup.sh 검토 — 안전하면 source 적용, 아니면 보류 사유를 보고.
- [ ] **Step 6:** 전체 테스트 + 셸 문법 통과.
- [ ] **Step 7:** 커밋 `refactor: 데이터/venv 경로 로직을 paths.py·lib_env.sh로 단일화`.

---

### Task 5: 문서/UX/보안 + 버전 1.7.0

**Files:**
- Modify: `commands/summarize.md`, `commands/stop.md`, `README.md`, `scripts/setup.sh`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`

**처리할 검증 항목:**
- 트리거 겹침(UX, low): "회의록 정리해줘"가 `stop.md`·`summarize.md` 양쪽 트리거. → `summarize.md`는 "파일로 회의록 정리해줘"처럼 파일 맥락을 명시하고, `stop.md`는 녹음 종료 맥락 트리거 유지. 겹치는 모호 표현 해소.
- summarize 파일 전달 불명확(UX, low): `summarize.md`에 "파일 경로 없이 트리거하면 경로를 되묻는다"는 한 줄 + 경로 포함 자연어 예시 추가.
- Git for Windows 안내 비대칭(문서, low): [README.md:48](README.md:48)에 설치 URL(https://git-scm.com/download/win)과 이유("Claude Desktop이 Bash 스크립트 실행에 필요") 보강.
- README 후행 슬래시(문서, low): [README.md:58](README.md:58)의 `~/Documents/meetings/`·`~/Desktop/meetings/` 후행 슬래시를 93·105행·config 기본값과 통일(제거).
- WHISPER_MODEL 코드 주입(보안, low): [setup.sh:80](scripts/setup.sh:80)의 `python3 -c "...WhisperModel('$WHISPER_MODEL'...)"`을 `sys.argv` 전달 방식으로 변경 — `python3 -c "import sys; from faster_whisper import WhisperModel; WhisperModel(sys.argv[1], ...)" "$WHISPER_MODEL"`.
- 버전 1.6.1 → 1.7.0 (plugin.json + marketplace.json).

**절차:**
- [ ] **Step 1:** summarize.md/stop.md 트리거 정리 + summarize 입력 안내 보강.
- [ ] **Step 2:** README Git for Windows 안내 + 슬래시 통일.
- [ ] **Step 3:** setup.sh WHISPER_MODEL을 sys.argv로. `bash -n scripts/setup.sh` 통과.
- [ ] **Step 4:** 버전 1.7.0(두 파일). `grep '"version"'` 일치 확인.
- [ ] **Step 5:** 전체 테스트 통과 + 커밋 `docs+fix: 트리거 겹침·Win 안내·슬래시·WHISPER_MODEL 주입 방어 + 1.7.0`.

---

## 완료 기준

- 모든 태스크의 테스트 통과, 전체 `pytest tests/ -q` 그린(신규 테스트 다수 추가).
- `bash -n scripts/*.sh` 문법 OK.
- `plugin.json`·`marketplace.json` 1.7.0 일치.
- 최종 whole-branch 리뷰 후 머지.
