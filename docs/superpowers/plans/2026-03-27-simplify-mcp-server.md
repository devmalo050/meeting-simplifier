# MCP 서버 단순화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** start.js/state 파일 제거 및 transcriber.js 단순화로 녹음·변환 안정성 확보

**Architecture:** `index.js`를 직접 실행 엔트리포인트로 변경. recorder.js는 state 파일 없이 인메모리만 사용. transcriber.js는 pendingResolve/workerStarting 복잡한 콜백 체인 없이 단순 async readline 방식으로 재작성. Python worker 상주 및 warmup은 그대로 유지.

**Tech Stack:** Node.js (ESM), Python (faster-whisper), node-record-lpcm16, @modelcontextprotocol/sdk

---

## 파일 구조

- **삭제:** `mcp-server/start.js` — 자식 프로세스 래퍼 불필요
- **수정:** `mcp-server/recorder.js` — state 파일 관련 코드 전부 제거, 인메모리만
- **수정:** `mcp-server/transcriber.js` — 단순 async readline 방식으로 재작성
- **수정:** `mcp-server/index.js` — setup.sh 백그라운드 실행 로직 추가 (start.js에 있던 것)
- **수정:** `.claude-plugin/plugin.json` — MCP 서버 실행 명령 `start.js` → `index.js`로 변경

---

### Task 1: plugin.json 실행 명령 변경

**Files:**
- Modify: `.claude-plugin/plugin.json`
- Modify: `marketplace.json` (동일 변경)

- [ ] **Step 1: marketplace.json 내용 확인**

```bash
cat marketplace.json
```

- [ ] **Step 2: plugin.json MCP 서버 실행 명령 확인**

현재 `mcpServers` 설정에서 `start.js`를 사용하는지 확인:
```bash
cat .claude-plugin/plugin.json
```

> 참고: 현재 plugin.json에는 mcpServers 설정이 없을 수 있음. Claude Code 전역 설정(`~/.claude/settings.json`)에서 meeting-simplifier MCP 서버 명령을 확인해야 할 수도 있음.

```bash
cat ~/.claude/settings.json | grep -A5 meeting-simplifier
```

- [ ] **Step 3: MCP 서버 실행 명령 위치 파악 후 start.js → index.js 변경**

`~/.claude/settings.json`에서 meeting-simplifier 항목을 찾아 `start.js` → `index.js`로 변경:

```json
"meeting-simplifier": {
  "command": "node",
  "args": ["/path/to/mcp-server/index.js"]
}
```

- [ ] **Step 4: 커밋 (아직 하지 않음 — index.js 수정 후 함께)**

---

### Task 2: index.js에 환경 설정 로직 추가

start.js가 담당하던 npm install, setup.sh 실행 로직을 index.js 상단으로 이동.

**Files:**
- Modify: `mcp-server/index.js`

- [ ] **Step 1: index.js 상단에 환경 설정 로직 추가**

`mcp-server/index.js` 상단 import 아래에 추가:

```js
import { execFileSync, spawn } from 'child_process';
import { existsSync } from 'fs';
import os from 'os';

const PLUGIN_ROOT = path.join(__dirname, '..');
const WHISPER_MODEL = process.env.WHISPER_MODEL ?? 'medium';

// npm install — MCP 서버 구동에 필수
if (!existsSync(path.join(PLUGIN_ROOT, 'node_modules', '@modelcontextprotocol'))) {
  try {
    execFileSync('npm', ['install', '--prefer-offline', '--quiet'], {
      cwd: PLUGIN_ROOT,
      stdio: ['ignore', 'ignore', 'inherit'],
    });
  } catch (e) {
    process.stderr.write(`[meeting-simplifier] npm install 실패: ${e.message}\n`);
  }
}

// setup.sh — venv/모델 설치, 백그라운드 실행
const venvPython = process.platform === 'win32'
  ? path.join(PLUGIN_ROOT, '.venv', 'Scripts', 'python.exe')
  : path.join(PLUGIN_ROOT, '.venv', 'bin', 'python');
const modelCache = path.join(os.homedir(), '.cache', 'huggingface', 'hub', `models--Systran--faster-whisper-${WHISPER_MODEL}`);

if (!existsSync(venvPython) || !existsSync(modelCache)) {
  const setupProc = process.platform === 'win32'
    ? spawn('powershell', ['-ExecutionPolicy', 'Bypass', '-File', path.join(PLUGIN_ROOT, 'scripts', 'setup.ps1')], {
        cwd: PLUGIN_ROOT, env: { ...process.env, WHISPER_MODEL }, stdio: 'ignore', detached: true,
      })
    : spawn('bash', [path.join(PLUGIN_ROOT, 'scripts', 'setup.sh')], {
        cwd: PLUGIN_ROOT, env: { ...process.env, WHISPER_MODEL }, stdio: 'ignore', detached: true,
      });
  setupProc.unref();
}
```

- [ ] **Step 2: index.js 기존 `PLUGIN_ROOT` 정의 제거 (중복 방지)**

기존 `const PLUGIN_ROOT = ...` 줄을 위 코드 블록으로 대체했으므로 중복 제거.

- [ ] **Step 3: SIGTERM 핸들러에 cleanupTempFiles 추가**

현재 SIGTERM 핸들러:
```js
process.on('SIGTERM', () => { killActiveTranscription(); process.exit(0); });
```

변경:
```js
process.on('SIGTERM', () => { killActiveTranscription(); cleanupTempFiles(); process.exit(0); });
```

- [ ] **Step 4: WHISPER_MODEL을 transcriber에 전달**

`warmupWorker()` 호출 위에:
```js
// WHISPER_MODEL 환경변수는 transcribe_server.py에서 직접 읽음 — process.env에 이미 설정됨
warmupWorker();
```

환경변수가 이미 `process.env.WHISPER_MODEL`로 전달되므로 별도 인자 불필요. 확인만.

- [ ] **Step 5: 커밋**

```bash
git add mcp-server/index.js
git commit -m "feat: index.js를 직접 실행 엔트리포인트로 — start.js 로직 흡수"
```

---

### Task 3: recorder.js — state 파일 제거

인메모리 `activeRecording`만 사용. 단일 인스턴스(start.js 제거)이므로 cross-process 통신 불필요.

**Files:**
- Modify: `mcp-server/recorder.js`

- [ ] **Step 1: recorder.js 전체를 아래 내용으로 교체**

```js
// mcp-server/recorder.js
import recorder from 'node-record-lpcm16';
import fs from 'fs';
import path from 'path';
import os from 'os';

// 인메모리 recording 핸들 — 단일 인스턴스이므로 state 파일 불필요
let activeRecording = null;

export function getLastAudioPath() {
  return activeRecording?.tempPath ?? null;
}

export function startRecording() {
  if (activeRecording) {
    return { error: '이미 녹음 중입니다. 먼저 녹음을 중지해주세요.' };
  }

  const tempPath = path.join(os.tmpdir(), `meeting-${Date.now()}.wav`);
  const fileStream = fs.createWriteStream(tempPath);

  let recording;
  try {
    recording = recorder.record({
      sampleRate: 16000,
      channels: 1,
      audioType: 'wav',
      recorder: process.platform === 'win32' ? 'sox' : 'rec',
    });
  } catch (err) {
    return { error: `녹음 시작 실패: ${err.message}\nsox/rec가 설치되어 있는지 확인하세요.` };
  }

  recording.stream().pipe(fileStream);

  recording.stream().on('error', (err) => {
    if (err.message.includes('permission') || err.message.includes('access')) {
      console.error(
        process.platform === 'darwin'
          ? '마이크 접근 권한이 없습니다. 시스템 환경설정 → 개인 정보 보호 → 마이크에서 터미널 권한을 허용해주세요.'
          : '마이크 접근 권한이 없습니다. 설정 → 개인 정보 → 마이크에서 앱 접근을 허용해주세요.'
      );
    }
    cleanupTempFiles();
  });

  activeRecording = { recording, tempPath, fileStream, startedAt: Date.now() };
  return { ok: true };
}

export function stopRecording() {
  if (!activeRecording) {
    return Promise.resolve({ error: '진행 중인 녹음이 없습니다.' });
  }

  const { recording, tempPath, fileStream, startedAt } = activeRecording;
  const duration = Math.round((Date.now() - startedAt) / 1000);
  activeRecording = null;

  try { recording.stop(); } catch {}
  try { fileStream.end(); } catch {}

  // 파일이 디스크에 플러시될 때까지 최대 5초 대기
  return new Promise((resolve) => {
    let waited = 0;
    const interval = setInterval(() => {
      waited += 200;
      try {
        const size = fs.existsSync(tempPath) ? fs.statSync(tempPath).size : 0;
        if (size > 0 || waited >= 5000) {
          clearInterval(interval);
          resolve(size > 0
            ? { audio_path: tempPath, duration_seconds: duration }
            : { error: '녹음 파일을 찾을 수 없습니다.' });
        }
      } catch {
        clearInterval(interval);
        resolve({ error: '녹음 파일을 찾을 수 없습니다.' });
      }
    }, 200);
  });
}

export function cleanupTempFiles() {
  if (!activeRecording) return;
  try { activeRecording.recording.stop(); } catch {}
  try { activeRecording.fileStream.destroy(); } catch {}
  try { fs.unlinkSync(activeRecording.tempPath); } catch {}
  activeRecording = null;
}
```

- [ ] **Step 2: 기존 state 파일 잔존물 정리**

```bash
rm -f /tmp/meeting-simplifier-state.json /tmp/meeting-simplifier-last-audio.json
```

- [ ] **Step 3: 커밋**

```bash
git add mcp-server/recorder.js
git commit -m "refactor: recorder.js state 파일 제거 — 인메모리만 사용"
```

---

### Task 4: transcriber.js — 단순 async readline 방식으로 재작성

`pendingResolve/pendingReject` 콜백 트릭과 `workerStarting` Promise 관리 제거. `readline` 인터페이스로 Python stdout 한 줄씩 비동기 읽기.

**Files:**
- Modify: `mcp-server/transcriber.js`

- [ ] **Step 1: transcriber.js 전체를 아래 내용으로 교체**

```js
// mcp-server/transcriber.js
// Python worker를 상주시켜 모델 로딩 1회만 수행 — 단순 readline 방식
import { spawn } from 'child_process';
import { createInterface } from 'readline';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PLUGIN_ROOT = path.join(__dirname, '..');
const PYTHON_SCRIPT = path.join(__dirname, 'transcribe_server.py');

function resolvePython() {
  const venvPython = process.platform === 'win32'
    ? path.join(PLUGIN_ROOT, '.venv', 'Scripts', 'python.exe')
    : path.join(PLUGIN_ROOT, '.venv', 'bin', 'python');
  if (fs.existsSync(venvPython)) return venvPython;
  return process.platform === 'win32' ? 'python' : 'python3';
}

let workerProc = null;
let workerReady = false;
let workerReadline = null;

function startWorker() {
  const python = resolvePython();
  const proc = spawn(python, [PYTHON_SCRIPT], {
    env: process.env,
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  workerProc = proc;
  workerReady = false;

  // readline으로 stdout 한 줄씩 읽기 (응답 대기에 사용)
  workerReadline = createInterface({ input: proc.stdout, crlfDelay: Infinity });

  proc.stderr.on('data', (d) => {
    for (const line of d.toString().split('\n')) {
      if (line.startsWith('READY:ok')) {
        workerReady = true;
      } else if (line.startsWith('PROGRESS:')) {
        const match = line.match(/PROGRESS:(\d+)\/(\d+)/);
        if (match && proc._onProgress) proc._onProgress(parseInt(match[1]), parseInt(match[2]));
      } else if (line.trim() && !line.startsWith('READY:')) {
        process.stderr.write(`[transcriber] ${line}\n`);
      }
    }
  });

  proc.on('error', (err) => {
    workerProc = null;
    workerReady = false;
    workerReadline = null;
  });

  proc.on('close', () => {
    workerProc = null;
    workerReady = false;
    workerReadline = null;
  });

  return proc;
}

// worker가 READY:ok 상태가 될 때까지 대기 (최대 5분)
function waitForReady(proc) {
  return new Promise((resolve, reject) => {
    if (workerReady) return resolve();
    const timeout = setTimeout(() => reject(new Error('Whisper 모델 로딩 타임아웃 (5분 초과)')), 5 * 60 * 1000);
    const check = setInterval(() => {
      if (!workerProc || workerProc !== proc) {
        clearInterval(check);
        clearTimeout(timeout);
        reject(new Error('Whisper worker 프로세스 종료됨'));
      } else if (workerReady) {
        clearInterval(check);
        clearTimeout(timeout);
        resolve();
      }
    }, 100);
  });
}

// readline에서 다음 줄 비동기로 읽기
function readNextLine(rl) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      reject(new Error('음성 변환 타임아웃 (10분 초과)'));
    }, 10 * 60 * 1000);

    rl.once('line', (line) => {
      clearTimeout(timeout);
      resolve(line);
    });
    rl.once('close', () => {
      clearTimeout(timeout);
      reject(new Error('Whisper 프로세스가 예기치 않게 종료됨'));
    });
  });
}

export async function transcribeAudio(audioPath, onProgress) {
  // worker가 없거나 죽었으면 새로 시작
  if (!workerProc || workerProc.killed) {
    startWorker();
  }

  const proc = workerProc;
  proc._onProgress = onProgress;

  await waitForReady(proc);

  proc.stdin.write(JSON.stringify({ audio_path: audioPath, language: null }) + '\n');

  const line = await readNextLine(workerReadline);
  const result = JSON.parse(line);
  if (result.error) throw new Error(result.error);
  if (!result.transcript || result.transcript.trim() === '') throw new Error('음성이 감지되지 않았습니다.');
  return result;
}

export function warmupWorker() {
  if (!workerProc || workerProc.killed) {
    startWorker();
  }
}

export function killActiveTranscription() {
  if (workerProc && !workerProc.killed) {
    try { workerProc.kill('SIGTERM'); } catch {}
  }
  workerProc = null;
  workerReady = false;
  workerReadline = null;
}
```

- [ ] **Step 2: 커밋**

```bash
git add mcp-server/transcriber.js
git commit -m "refactor: transcriber.js — pendingResolve 제거, 단순 readline 방식으로 재작성"
```

---

### Task 5: start.js 삭제 및 MCP 실행 명령 업데이트

**Files:**
- Delete: `mcp-server/start.js`
- Modify: `~/.claude/settings.json` (MCP 서버 실행 명령)

- [ ] **Step 1: 현재 MCP 서버 실행 명령 확인**

```bash
cat ~/.claude/settings.json | python3 -m json.tool | grep -A10 meeting-simplifier
```

- [ ] **Step 2: settings.json에서 start.js → index.js 변경**

`~/.claude/settings.json`의 meeting-simplifier MCP 서버 args에서 `start.js` → `index.js`로 수정.

예시 (실제 경로는 Step 1 결과 기준):
```json
"meeting-simplifier": {
  "command": "node",
  "args": ["/Users/ain/Projects/meeting-simplifier/mcp-server/index.js"],
  "env": { "WHISPER_MODEL": "medium" }
}
```

- [ ] **Step 3: start.js 삭제**

```bash
rm mcp-server/start.js
```

- [ ] **Step 4: 커밋**

```bash
git add -A mcp-server/start.js
git commit -m "feat: start.js 삭제 — index.js 직접 실행으로 단순화"
```

---

### Task 6: 동작 검증

- [ ] **Step 1: Claude Code 재시작 (MCP 서버 리로드)**

Claude Code를 재시작하거나 `/mcp` 명령으로 meeting-simplifier 서버 재연결.

- [ ] **Step 2: 녹음 시작 테스트**

meeting-simplifier start skill 실행 → 녹음 시작 확인.

- [ ] **Step 3: 30초 대기 후 stop**

아무 작업 없이 30초 대기 → stop 실행 → WAV 파일 경로 반환 확인.

- [ ] **Step 4: 프로세스 중복 없음 확인**

```bash
ps aux | grep -E "node|python" | grep -v grep
```

`index.js` 1개, `transcribe_server.py` 1개만 있어야 함 (start.js 없음).

- [ ] **Step 5: 변환 테스트**

stop 후 transcribe → 회의록 생성까지 정상 동작 확인.

- [ ] **Step 6: 버전 bump 및 최종 커밋**

```bash
# .claude-plugin/plugin.json 버전 올리기 (예: 1.3.48 → 1.3.49)
git add .claude-plugin/plugin.json
git commit -m "chore: v1.3.49 — MCP 서버 단순화 (start.js 제거, state 파일 제거, transcriber readline 방식)"
```

