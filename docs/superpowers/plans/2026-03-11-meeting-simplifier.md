# Meeting Simplifier Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 회의 녹음 → Whisper STT → Claude 회의록 생성까지 자동화하는 Claude Code 플러그인 구축

**Architecture:** Node.js MCP 서버가 녹음(node-record-lpcm16), Whisper 변환(faster-whisper subprocess), 파일 저장(md/txt/docx)을 담당하고, Skills가 자연어/명령어 트리거와 Claude 오케스트레이션을 담당한다.

**Tech Stack:** Node.js 18+, @modelcontextprotocol/sdk, node-record-lpcm16, sox, faster-whisper (Python), docx (npm)

**병렬 실행 가이드 (서브에이전트 사용 시):**
```
[Wave 1 — 병렬]  Task 1 (scaffolding) + Task 2 (check-deps)
[Wave 2 — 병렬]  Task 3 (recorder) + Task 4 (transcriber) + Task 5 (exporter)
[Wave 3 — 순차]  Task 6 (index.js) → Task 7 (skills) → Task 8 (검증)
```
- Wave 2는 Wave 1 완료 후 시작 (package.json, node_modules 필요)
- Task 6은 Task 3, 4, 5를 모두 import하므로 Wave 2 완료 후 시작
- Task 7, 8은 순차 실행

---

## File Map

| 파일 | 역할 |
|------|------|
| `.claude-plugin/plugin.json` | 플러그인 메타데이터 |
| `.mcp.json` | MCP 서버 연결 설정 |
| `settings.json` | 기본 사용자 설정 |
| `package.json` | Node.js 의존성 |
| `mcp-server/index.js` | MCP 서버 진입점, 도구 등록 |
| `mcp-server/recorder.js` | 마이크 녹음 (node-record-lpcm16), 상태 관리 |
| `mcp-server/transcriber.js` | faster-whisper subprocess 호출, 청크 처리 |
| `mcp-server/transcribe.py` | faster-whisper Python 헬퍼 스크립트 |
| `mcp-server/exporter.js` | md/txt/docx 파일 저장, 디렉토리 생성 |
| `.gitignore` | node_modules, 임시 WAV 파일 제외 |
| `skills/start/SKILL.md` | 녹음 시작 skill |
| `skills/stop/SKILL.md` | 녹음 중지 + 회의록 생성 skill |
| `skills/summarize/SKILL.md` | 기존 파일로 회의록 생성 skill |
| `scripts/check-deps.js` | sox/faster-whisper 설치 검증 스크립트 |

---

## Chunk 1: 프로젝트 초기 설정

### Task 1: package.json 및 플러그인 메타데이터 생성

**Files:**
- Create: `package.json`
- Create: `.claude-plugin/plugin.json`
- Create: `.mcp.json`
- Create: `settings.json`

- [ ] **Step 1: package.json 생성**

```json
{
  "name": "meeting-simplifier",
  "version": "1.0.0",
  "description": "Claude 플러그인 — 회의 녹음 및 회의록 자동 생성",
  "type": "module",
  "main": "mcp-server/index.js",
  "scripts": {
    "start": "node mcp-server/index.js",
    "check-deps": "node scripts/check-deps.js"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.0.0",
    "node-record-lpcm16": "^1.0.1",
    "docx": "^8.5.0"
  }
}
```

- [ ] **Step 2: .claude-plugin/plugin.json 생성**

```bash
mkdir -p .claude-plugin
```

```json
{
  "name": "meeting-simplifier",
  "description": "회의 녹음 및 회의록 자동 생성",
  "version": "1.0.0",
  "author": { "name": "ain" }
}
```

- [ ] **Step 3: .mcp.json 생성**

```json
{
  "mcpServers": {
    "meeting-simplifier": {
      "command": "node",
      "args": ["mcp-server/index.js"],
      "env": {}
    }
  }
}
```

- [ ] **Step 4: settings.json 생성**

```json
{
  "meeting-simplifier": {
    "output_dir": "~/Documents/meetings",
    "output_format": "md",
    "output_language": "auto"
  }
}
```

- [ ] **Step 5: npm install**

```bash
npm install
```

Expected: `node_modules/` 생성, 에러 없음

- [ ] **Step 6: .gitignore 생성**

```
node_modules/
*.wav
*.tmp
```

- [ ] **Step 7: Commit**

```bash
git add package.json package-lock.json .claude-plugin/plugin.json .mcp.json settings.json .gitignore
git commit -m "chore: initialize project structure and dependencies"
```

---

## Chunk 2: 의존성 검증 스크립트

### Task 2: sox / faster-whisper 설치 검증 스크립트

**Files:**
- Create: `scripts/check-deps.js`

- [ ] **Step 1: check-deps.js 작성**

```bash
mkdir -p scripts
```

```js
// scripts/check-deps.js
import { execSync } from 'child_process';

const checks = [
  {
    name: 'sox/rec',
    command: 'rec --version',
    installHint: {
      darwin: 'brew install sox',
      win32: 'https://sourceforge.net/projects/sox/files/sox/ 에서 직접 설치 후 PATH 추가',
    },
  },
  {
    name: 'faster-whisper',
    command: 'python3 -c "import faster_whisper"',
    installHint: {
      darwin: 'pip install faster-whisper',
      win32: 'pip install faster-whisper',
    },
  },
];

let allOk = true;
for (const check of checks) {
  try {
    execSync(check.command, { stdio: 'ignore' });
    console.log(`✅ ${check.name}`);
  } catch {
    const hint = check.installHint[process.platform] ?? check.installHint['darwin'];
    console.error(`❌ ${check.name} 미설치\n   설치: ${hint}`);
    allOk = false;
  }
}

if (!allOk) process.exit(1);
console.log('\n모든 의존성이 설치되어 있습니다.');
```

- [ ] **Step 2: 스크립트 실행하여 동작 확인**

```bash
node scripts/check-deps.js
```

Expected: sox/faster-whisper 설치 상태에 따라 ✅ 또는 ❌ + 설치 안내 출력

- [ ] **Step 3: Commit**

```bash
git add scripts/check-deps.js
git commit -m "chore: add dependency check script for sox and faster-whisper"
```

---

## Chunk 3: recorder.js — 녹음 모듈

### Task 3: 마이크 녹음 모듈 작성

**Files:**
- Create: `mcp-server/recorder.js`

- [ ] **Step 1: mcp-server 디렉토리 생성**

```bash
mkdir -p mcp-server
```

- [ ] **Step 2: recorder.js 작성**

```js
// mcp-server/recorder.js
import recorder from 'node-record-lpcm16';
import fs from 'fs';
import path from 'path';
import os from 'os';

let activeRecording = null; // { recording, tempPath }

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
      console.error('마이크 접근 권한이 없습니다.');
      console.error(
        process.platform === 'darwin'
          ? '시스템 환경설정 → 개인 정보 보호 → 마이크에서 터미널 권한을 허용해주세요.'
          : '설정 → 개인 정보 → 마이크에서 앱 접근을 허용해주세요.'
      );
    }
  });

  activeRecording = { recording, tempPath, fileStream };
  return { ok: true };
}

export function stopRecording() {
  if (!activeRecording) {
    return { error: '진행 중인 녹음이 없습니다.' };
  }

  const { recording, tempPath, fileStream } = activeRecording;

  return new Promise((resolve) => {
    fileStream.on('finish', () => {
      activeRecording = null;
      resolve({ audio_path: tempPath });
    });
    recording.stop();
  });
}

export function cleanupTempFiles() {
  if (activeRecording) {
    try {
      activeRecording.recording.stop();
      fs.unlinkSync(activeRecording.tempPath);
    } catch {}
    activeRecording = null;
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add mcp-server/recorder.js
git commit -m "feat: add recorder module with start/stop and cleanup"
```

---

## Chunk 4: transcriber.js — Whisper STT 모듈

### Task 4: faster-whisper subprocess 호출 모듈

**Files:**
- Create: `mcp-server/transcriber.js`
- Create: `mcp-server/transcribe.py`

- [ ] **Step 1: transcribe.py (Python 헬퍼) 작성**

긴 녹음은 10분(600초) 청크로 분할 처리, 각 청크 완료 시 진행률을 stderr로 보고.

```python
# mcp-server/transcribe.py
import sys
import json
import os
import wave
import struct
from faster_whisper import WhisperModel

CHUNK_SECS = 600   # 10분
OVERLAP_SECS = 30  # 30초 오버랩
SAMPLE_RATE = 16000

def read_wav_duration(path):
    try:
        with wave.open(path, 'r') as f:
            return f.getnframes() / f.getframerate()
    except Exception:
        return 0

def split_wav(path, chunk_secs, overlap_secs):
    """WAV 파일을 청크로 분할하여 임시 파일 경로 리스트 반환."""
    import tempfile
    with wave.open(path, 'r') as f:
        params = f.getparams()
        frame_rate = f.getframerate()
        n_channels = f.getnchannels()
        sampwidth = f.getsampwidth()
        total_frames = f.getnframes()
        chunk_frames = int(chunk_secs * frame_rate)
        overlap_frames = int(overlap_secs * frame_rate)
        step_frames = chunk_frames - overlap_frames

        chunks = []
        offset = 0
        while offset < total_frames:
            end = min(offset + chunk_frames, total_frames)
            f.setpos(offset)
            frames = f.readframes(end - offset)

            tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            with wave.open(tmp.name, 'w') as out:
                out.setparams(params)
                out.writeframes(frames)
            chunks.append(tmp.name)
            offset += step_frames

    return chunks

def transcribe(audio_path):
    model = WhisperModel("large-v3", device="auto", compute_type="auto")

    duration = read_wav_duration(audio_path)
    # 청크 분할은 WAV만 지원 (MP3/M4A는 faster-whisper 내부 처리)
    is_long = duration > CHUNK_SECS and audio_path.lower().endswith('.wav')

    if is_long:
        chunk_paths = split_wav(audio_path, CHUNK_SECS, OVERLAP_SECS)
        total = len(chunk_paths)
        all_text = []
        detected_language = 'ko'

        for i, chunk_path in enumerate(chunk_paths, 1):
            print(f"PROGRESS:{i}/{total}", file=sys.stderr, flush=True)
            segments, info = model.transcribe(chunk_path, language=None, beam_size=5)
            text = " ".join(s.text.strip() for s in segments)
            all_text.append(text)
            detected_language = info.language
            os.unlink(chunk_path)

        transcript = " ".join(all_text)
        language = detected_language
    else:
        segments, info = model.transcribe(audio_path, language=None, beam_size=5)
        transcript = " ".join(s.text.strip() for s in segments)
        language = info.language

    print(json.dumps({"transcript": transcript, "language": language}, ensure_ascii=False))

if __name__ == "__main__":
    audio_path = sys.argv[1]
    transcribe(audio_path)
```

- [ ] **Step 2: transcriber.js 작성**

```js
// mcp-server/transcriber.js
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PYTHON_SCRIPT = path.join(__dirname, 'transcribe.py');
const PYTHON_CMD = process.platform === 'win32' ? 'python' : 'python3';

export async function transcribeAudio(audioPath, onProgress) {
  return new Promise((resolve, reject) => {
    const proc = spawn(PYTHON_CMD, [PYTHON_SCRIPT, audioPath]);
    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (d) => (stdout += d));
    proc.stderr.on('data', (d) => {
      const line = d.toString();
      stderr += line;
      // 청크 진행률 보고: "PROGRESS:2/5" 형태
      const match = line.match(/PROGRESS:(\d+)\/(\d+)/);
      if (match && onProgress) {
        onProgress(parseInt(match[1]), parseInt(match[2]));
      }
    });

    proc.on('close', (code) => {
      if (code !== 0) {
        if (stderr.includes('ModuleNotFoundError') || stderr.includes('No module named')) {
          reject(new Error('faster-whisper가 설치되어 있지 않습니다.\n실행: pip install faster-whisper'));
        } else {
          reject(new Error(`Whisper 변환 실패: ${stderr}`));
        }
        return;
      }

      try {
        const result = JSON.parse(stdout.trim());
        if (!result.transcript) {
          resolve({ transcript: '', language: 'ko', empty: true });
        } else {
          resolve(result);
        }
      } catch {
        reject(new Error(`Whisper 결과 파싱 실패: ${stdout}`));
      }
    });
  });
}
```

- [ ] **Step 3: Commit**

```bash
git add mcp-server/transcriber.js mcp-server/transcribe.py
git commit -m "feat: add transcriber module with faster-whisper subprocess"
```

---

## Chunk 5: exporter.js — 파일 저장 모듈

### Task 5: 회의록 파일 저장 모듈 (md/txt/docx)

**Files:**
- Create: `mcp-server/exporter.js`

- [ ] **Step 1: exporter.js 작성**

```js
// mcp-server/exporter.js
import fs from 'fs';
import path from 'path';
import os from 'os';
import { Document, Packer, Paragraph, HeadingLevel, TextRun } from 'docx';

function resolvePath(p) {
  return p.startsWith('~') ? path.join(os.homedir(), p.slice(1)) : p;
}

function sanitizeDirName(title) {
  // 파일명에 사용할 수 없는 문자 제거, 공백을 하이픈으로
  return title.replace(/[<>:"/\\|?*]/g, '').replace(/\s+/g, '-').slice(0, 80);
}

export async function saveMeeting({ title, transcript, minutes, audioPath, format, outputDir }) {
  const resolvedBase = resolvePath(outputDir);
  const date = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
  const dirName = sanitizeDirName(`${date}-${title}`);
  const meetingDir = path.join(resolvedBase, dirName);

  try {
    fs.mkdirSync(meetingDir, { recursive: true });
  } catch (err) {
    if (err.code === 'EACCES' || err.code === 'EPERM') {
      // 권한 없으면 바탕화면으로 대체
      const fallback = path.join(os.homedir(), 'Desktop', dirName);
      fs.mkdirSync(fallback, { recursive: true });
      return saveMeeting({ title, transcript, minutes, audioPath, format, outputDir: path.join(os.homedir(), 'Desktop') });
    }
    throw err;
  }

  // 녹음 파일 이동 (임시 → 최종 위치), 텍스트 파일 입력 시 audioPath가 빈 문자열일 수 있음
  if (audioPath) {
    const audioExt = path.extname(audioPath) || '.wav';
    const finalAudioPath = path.join(meetingDir, `recording${audioExt}`);
    fs.renameSync(audioPath, finalAudioPath);
  }

  // 회의록 저장
  const minutesFileName = `minutes.${format}`;
  const minutesPath = path.join(meetingDir, minutesFileName);

  if (format === 'md' || format === 'txt') {
    fs.writeFileSync(minutesPath, minutes, 'utf-8');
  } else if (format === 'docx') {
    await saveDocx(minutesPath, title, minutes);
  }

  return { saved_dir: meetingDir };
}

async function saveDocx(filePath, title, minutes) {
  // 마크다운 텍스트를 DOCX 단락으로 변환 (간단 처리)
  const lines = minutes.split('\n');
  const children = lines.map((line) => {
    if (line.startsWith('# ')) {
      return new Paragraph({ text: line.slice(2), heading: HeadingLevel.HEADING_1 });
    } else if (line.startsWith('## ')) {
      return new Paragraph({ text: line.slice(3), heading: HeadingLevel.HEADING_2 });
    } else if (line.startsWith('### ')) {
      return new Paragraph({ text: line.slice(4), heading: HeadingLevel.HEADING_3 });
    } else {
      return new Paragraph({ children: [new TextRun(line)] });
    }
  });

  const doc = new Document({ sections: [{ children }] });
  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(filePath, buffer);
}
```

- [ ] **Step 2: Commit**

```bash
git add mcp-server/exporter.js
git commit -m "feat: add exporter module for md/txt/docx output"
```

---

## Chunk 6: MCP 서버 진입점

### Task 6: index.js — MCP 서버 및 도구 등록

**Files:**
- Create: `mcp-server/index.js`

- [ ] **Step 1: index.js 작성**

```js
// mcp-server/index.js
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { startRecording, stopRecording, cleanupTempFiles } from './recorder.js';
import { transcribeAudio } from './transcriber.js';
import { saveMeeting } from './exporter.js';

const server = new Server(
  { name: 'meeting-simplifier', version: '1.0.0' },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: 'meeting_record_start',
      description: '마이크 녹음을 시작합니다.',
      inputSchema: { type: 'object', properties: {} },
    },
    {
      name: 'meeting_record_stop',
      description: '녹음을 중지하고 WAV 파일 경로를 반환합니다.',
      inputSchema: { type: 'object', properties: {} },
    },
    {
      name: 'meeting_transcribe',
      description: '오디오 파일을 텍스트로 변환합니다 (Whisper large-v3).',
      inputSchema: {
        type: 'object',
        properties: {
          audio_path: { type: 'string', description: '변환할 오디오 파일 경로 (WAV/MP3/M4A)' },
        },
        required: ['audio_path'],
      },
    },
    {
      name: 'meeting_save',
      description: '회의록과 녹음 파일을 지정 디렉토리에 저장합니다.',
      inputSchema: {
        type: 'object',
        properties: {
          title: { type: 'string', description: '회의 제목 (디렉토리명에 사용)' },
          transcript: { type: 'string', description: 'Whisper 원문 트랜스크립트' },
          minutes: { type: 'string', description: '회의록 본문 (마크다운)' },
          audio_path: { type: 'string', description: '저장할 녹음 파일 경로' },
          format: { type: 'string', enum: ['md', 'txt', 'docx'], description: '출력 포맷' },
          output_dir: { type: 'string', description: '저장 기본 디렉토리' },
        },
        required: ['title', 'transcript', 'minutes', 'audio_path', 'format', 'output_dir'],
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    if (name === 'meeting_record_start') {
      const result = startRecording();
      return { content: [{ type: 'text', text: JSON.stringify(result) }] };
    }

    if (name === 'meeting_record_stop') {
      const result = await stopRecording();
      return { content: [{ type: 'text', text: JSON.stringify(result) }] };
    }

    if (name === 'meeting_transcribe') {
      const { audio_path } = args;
      const result = await transcribeAudio(audio_path, (current, total) => {
        // 청크 진행률을 stderr로 출력 (MCP 클라이언트가 표시)
        process.stderr.write(`변환 중... ${current}/${total} 청크 완료\n`);
      });
      if (result.empty) {
        return {
          content: [{ type: 'text', text: JSON.stringify({ error: '음성이 감지되지 않았습니다.' }) }],
        };
      }
      return { content: [{ type: 'text', text: JSON.stringify(result) }] };
    }

    if (name === 'meeting_save') {
      const { title, transcript, minutes, audio_path, format, output_dir } = args;
      const result = await saveMeeting({ title, transcript, minutes, audioPath: audio_path, format, outputDir: output_dir });
      return { content: [{ type: 'text', text: JSON.stringify(result) }] };
    }

    return { content: [{ type: 'text', text: JSON.stringify({ error: `알 수 없는 도구: ${name}` }) }] };
  } catch (err) {
    return { content: [{ type: 'text', text: JSON.stringify({ error: err.message }) }] };
  }
});

// 프로세스 종료 시 임시 파일 정리
process.on('SIGINT', () => { cleanupTempFiles(); process.exit(0); });
process.on('SIGTERM', () => { cleanupTempFiles(); process.exit(0); });

const transport = new StdioServerTransport();
await server.connect(transport);
```

- [ ] **Step 2: MCP 서버 기동 테스트**

```bash
node mcp-server/index.js
```

Expected: 에러 없이 실행, Ctrl+C로 종료

- [ ] **Step 3: Commit**

```bash
git add mcp-server/index.js
git commit -m "feat: add MCP server with all four tools registered"
```

---

## Chunk 7: Skills 작성

### Task 7: start / stop / summarize SKILL.md

**Files:**
- Create: `skills/start/SKILL.md`
- Create: `skills/stop/SKILL.md`
- Create: `skills/summarize/SKILL.md`

- [ ] **Step 1: skills 디렉토리 생성**

```bash
mkdir -p skills/start skills/stop skills/summarize
```

- [ ] **Step 2: skills/start/SKILL.md 작성**

```markdown
---
description: >
  회의 녹음을 시작합니다.
  트리거: "회의 녹음 시작해줘", "녹음 시작", "녹음해줘", "회의 시작할게", "미팅 시작해",
  "회의 시작", "지금부터 회의 녹음", "회의 들어갈게",
  "record meeting", "start recording", "start meeting"
---

`meeting_record_start` 도구를 호출하세요.

성공하면 다음과 같이 사용자에게 알려주세요:
"녹음을 시작했습니다. 회의가 끝나면 '녹음 끝' 또는 '회의록 만들어줘' 라고 말씀해주세요."

에러가 반환되면 에러 메시지를 그대로 사용자에게 전달하세요.
```

- [ ] **Step 3: skills/stop/SKILL.md 작성**

```markdown
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

2. `meeting_transcribe` 도구를 호출합니다. (`audio_path`는 이전 단계 결과 사용)
   - 변환 중임을 사용자에게 알립니다: "녹음을 텍스트로 변환 중입니다..."
   - 에러 반환 시 사용자에게 알리고 중단합니다.

3. 트랜스크립트를 바탕으로 다음 항목을 분석합니다:
   - **회의 제목**: 내용을 보고 간결한 한국어 제목 생성 (예: "분기-마케팅-전략-회의")
   - **언어**: 트랜스크립트 주요 언어로 회의록 작성 (설정이 ko/en이면 해당 언어 사용)

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
   - `audio_path`: 녹음 파일 경로
   - `format`: 사용자 설정값 (없으면 "md")
   - `output_dir`: 사용자 설정값 (없으면 "~/Documents/meetings")

6. 완료 후 사용자에게 알립니다:
"회의록이 저장되었습니다: {saved_dir}"
```

- [ ] **Step 4: skills/summarize/SKILL.md 작성**

```markdown
---
description: >
  기존 오디오 또는 텍스트 파일로 회의록을 생성합니다.
  트리거: "이 파일 회의록으로 정리해줘", "녹음 파일 분석해줘", "파일 첨부할게 회의록 만들어줘",
  "summarize this recording", "make minutes from this file"
---

`$ARGUMENTS`에 파일 경로가 제공된 경우 해당 경로를 사용합니다.
파일 경로가 없으면 사용자에게 파일 경로를 요청하세요.

파일 확장자에 따라 처리합니다:
- `.wav`, `.mp3`, `.m4a` → `meeting_transcribe` 도구로 먼저 변환 후 진행
- `.txt`, `.md` → 파일 내용을 직접 트랜스크립트로 사용

이후 `/meeting-simplifier:stop` skill의 3~6번 단계와 동일하게 진행합니다.
(회의록 작성 → `meeting_save` 호출 → 완료 안내)

단, `meeting_save`의 `audio_path`는 오디오 파일인 경우 해당 파일 경로,
텍스트 파일인 경우 빈 문자열("")을 전달합니다.
```

- [ ] **Step 5: Commit**

```bash
git add skills/
git commit -m "feat: add start/stop/summarize skills with natural language triggers"
```

---

## Chunk 8: 통합 검증

### Task 8: 전체 플러그인 동작 검증

**Files:**
- 없음 (기존 파일 검증)

- [ ] **Step 1: 의존성 검증 스크립트 실행**

```bash
node scripts/check-deps.js
```

Expected: sox, faster-whisper 모두 ✅

- [ ] **Step 2: MCP 서버 문법 오류 확인**

```bash
node --check mcp-server/index.js
node --check mcp-server/recorder.js
node --check mcp-server/transcriber.js
node --check mcp-server/exporter.js
```

Expected: 에러 없음

- [ ] **Step 3: 플러그인 로컬 테스트**

```bash
claude --plugin-dir .
```

Expected: Claude Code가 플러그인을 인식하고 `/meeting-simplifier:start`, `/meeting-simplifier:stop`, `/meeting-simplifier:summarize` 명령어 사용 가능

- [ ] **Step 4: start → stop 흐름 수동 테스트**

Claude Code 또는 Claude Desktop에서:
1. "녹음 시작해줘" 입력 → "녹음을 시작했습니다" 응답 확인
2. 5~10초 말하기
3. "녹음 끝" 입력 → 트랜스크립트 및 회의록 생성 확인
4. `~/Documents/meetings/` 아래 디렉토리 생성 및 파일 저장 확인

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete meeting-simplifier Claude plugin v1.0.0"
```
