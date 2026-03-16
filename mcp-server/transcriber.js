// mcp-server/transcriber.js
// Python 프로세스를 상주시켜 모델 로딩 1회만 수행
import { spawn } from 'child_process';
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
let pendingResolve = null;   // 현재 진행 중인 transcribe의 resolve
let pendingReject = null;
let stdoutBuf = '';

function getOrStartWorker(onProgress) {
  if (workerProc && !workerProc.killed) {
    return Promise.resolve(workerProc);
  }

  return new Promise((resolve, reject) => {
    const python = resolvePython();
    const proc = spawn(python, [PYTHON_SCRIPT], {
      env: process.env,
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    proc.stderr.on('data', (d) => {
      const lines = d.toString().split('\n');
      for (const line of lines) {
        if (line.startsWith('READY:ok')) {
          workerReady = true;
          workerProc = proc;
          resolve(proc);
        } else if (line.startsWith('READY:')) {
          // loading 메시지 — 무시
        } else if (line.startsWith('PROGRESS:')) {
          const match = line.match(/PROGRESS:(\d+)\/(\d+)/);
          const cb = proc._onProgress;
          if (match && cb) cb(parseInt(match[1]), parseInt(match[2]));
        } else if (line.trim()) {
          process.stderr.write(`[transcriber] ${line}\n`);
        }
      }
    });

    proc.stdout.on('data', (d) => {
      stdoutBuf += d.toString();
      let nl;
      while ((nl = stdoutBuf.indexOf('\n')) !== -1) {
        const jsonLine = stdoutBuf.slice(0, nl);
        stdoutBuf = stdoutBuf.slice(nl + 1);
        if (!jsonLine.trim()) continue;
        if (pendingResolve) {
          const res = pendingResolve;
          const rej = pendingReject;
          pendingResolve = null;
          pendingReject = null;
          try {
            const result = JSON.parse(jsonLine);
            if (result.error) rej(new Error(result.error));
            else if (!result.transcript || result.transcript.trim() === '') rej(new Error('음성이 감지되지 않았습니다.'));
            else res(result);
          } catch {
            rej(new Error(`Whisper 결과 파싱 실패: ${jsonLine}`));
          }
        }
      }
    });

    proc.on('error', (err) => {
      workerProc = null;
      workerReady = false;
      if (err.code === 'ENOENT') reject(new Error(`Python을 찾을 수 없습니다 (${python}). Python 3.9 이상을 설치해주세요.`));
      else reject(err);
      if (pendingReject) { pendingReject(err); pendingResolve = null; pendingReject = null; }
    });

    proc.on('close', (code) => {
      const wasReady = workerReady; // close 전 상태 저장
      workerProc = null;
      workerReady = false;
      if (pendingReject) {
        pendingReject(new Error(`Whisper 프로세스 종료 (code ${code})`));
        pendingResolve = null;
        pendingReject = null;
      }
      // READY:ok를 받기 전에 종료된 경우에만 시작 실패 reject
      if (!wasReady) reject(new Error(`Whisper 프로세스 시작 실패 (code ${code})`));
    });
  });
}

export async function transcribeAudio(audioPath, onProgress) {
  const proc = await getOrStartWorker(onProgress);

  // onProgress 콜백을 stderr 핸들러에 연결 (요청별로 교체)
  // stderr 이벤트는 getOrStartWorker에서 이미 등록됨 — onProgress를 교체
  proc._onProgress = onProgress;

  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      if (pendingReject) {
        pendingResolve = null;
        pendingReject = null;
        reject(new Error('음성 변환 타임아웃 (10분 초과). 녹음 파일이 너무 크거나 시스템이 응답하지 않습니다.'));
      }
    }, 10 * 60 * 1000); // 10분

    pendingResolve = (result) => { clearTimeout(timeout); resolve(result); };
    pendingReject = (err) => { clearTimeout(timeout); reject(err); };
    proc.stdin.write(JSON.stringify({ audio_path: audioPath }) + '\n');
  });
}

export function killActiveTranscription() {
  if (workerProc && !workerProc.killed) {
    try { workerProc.kill('SIGTERM'); } catch {}
    workerProc = null;
    workerReady = false;
  }
}
