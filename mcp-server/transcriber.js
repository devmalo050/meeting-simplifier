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
