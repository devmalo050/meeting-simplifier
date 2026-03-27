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
let workerReadline = null;
let workerReadyPromise = null; // READY:ok 이벤트 기반 대기 Promise

// 동시 transcribeAudio 호출을 직렬화하기 위한 큐
let transcribeQueue = Promise.resolve();

function startWorker() {
  const python = resolvePython();
  const proc = spawn(python, [PYTHON_SCRIPT], {
    env: process.env,
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  workerProc = proc;
  workerReadline = createInterface({ input: proc.stdout, crlfDelay: Infinity });

  // READY:ok 이벤트 기반 대기 — 폴링 불필요
  workerReadyPromise = new Promise((resolve, reject) => {
    const timeout = setTimeout(
      () => reject(new Error('Whisper 모델 로딩 타임아웃 (5분 초과)')),
      5 * 60 * 1000
    );
    proc.stderr.on('data', function onStderr(d) {
      for (const line of d.toString().split('\n')) {
        if (line.startsWith('READY:ok')) {
          clearTimeout(timeout);
          proc.stderr.removeListener('data', onStderr);
          resolve();
        } else if (line.startsWith('PROGRESS:')) {
          const match = line.match(/PROGRESS:(\d+)\/(\d+)/);
          if (match && proc._onProgress) proc._onProgress(parseInt(match[1]), parseInt(match[2]));
        } else if (line.trim() && !line.startsWith('READY:')) {
          process.stderr.write(`[transcriber] ${line}\n`);
        }
      }
    });
    proc.on('close', () => {
      clearTimeout(timeout);
      reject(new Error('Whisper worker 프로세스 종료됨'));
    });
  });

  proc.on('error', () => {
    workerProc = null;
    workerReadline = null;
    workerReadyPromise = null;
  });

  proc.on('close', () => {
    workerProc = null;
    workerReadline = null;
    workerReadyPromise = null;
  });

  return proc;
}

// readline에서 다음 줄 비동기로 읽기 — 상호 핸들러 제거로 누수 방지
function readNextLine(rl) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      rl.removeListener('line', onLine);
      rl.removeListener('close', onClose);
      reject(new Error('음성 변환 타임아웃 (10분 초과)'));
    }, 10 * 60 * 1000);

    function onLine(line) {
      clearTimeout(timeout);
      rl.removeListener('close', onClose);
      resolve(line);
    }

    function onClose() {
      clearTimeout(timeout);
      rl.removeListener('line', onLine);
      reject(new Error('Whisper 프로세스가 예기치 않게 종료됨'));
    }

    rl.once('line', onLine);
    rl.once('close', onClose);
  });
}

export async function transcribeAudio(audioPath, onProgress) {
  // 동시 호출 직렬화 — 큐에 넣어 순차 실행
  const result = await (transcribeQueue = transcribeQueue.then(() =>
    _doTranscribe(audioPath, onProgress)
  ));
  return result;
}

async function _doTranscribe(audioPath, onProgress) {
  if (!workerProc || workerProc.killed) {
    startWorker();
  }

  workerProc._onProgress = onProgress;

  await workerReadyPromise;

  workerProc.stdin.write(JSON.stringify({ audio_path: audioPath, language: null }) + '\n');

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
  workerReadline = null;
  workerReadyPromise = null;
}
