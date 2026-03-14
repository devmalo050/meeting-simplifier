// mcp-server/transcriber.js
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

import fs from 'fs';
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PLUGIN_ROOT = path.join(__dirname, '..');
const PYTHON_SCRIPT = path.join(__dirname, 'transcribe.py');

// venv Python 우선 사용 (PEP 668 시스템 패키지 보호 우회)
function resolvePython() {
  const venvPython = process.platform === 'win32'
    ? path.join(PLUGIN_ROOT, '.venv', 'Scripts', 'python.exe')
    : path.join(PLUGIN_ROOT, '.venv', 'bin', 'python');
  if (fs.existsSync(venvPython)) return venvPython;
  return process.platform === 'win32' ? 'python' : 'python3';
}
export async function transcribeAudio(audioPath, onProgress) {
  const PYTHON_CMD = resolvePython();
  return new Promise((resolve, reject) => {
    const proc = spawn(PYTHON_CMD, [PYTHON_SCRIPT, audioPath]);
    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (d) => (stdout += d));
    proc.stderr.on('data', (d) => {
      const line = d.toString();
      stderr += line;
      // Report chunk progress: "PROGRESS:2/5" format
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
        if (result.error) {
          reject(new Error(result.error));
        } else if (!result.transcript || result.transcript.trim() === '') {
          reject(new Error('음성이 감지되지 않았습니다.'));
        } else {
          resolve(result);
        }
      } catch {
        reject(new Error(`Whisper 결과 파싱 실패: ${stdout}`));
      }
    });

    proc.on('error', (err) => {
      if (err.code === 'ENOENT') {
        reject(new Error(`Python을 찾을 수 없습니다 (${PYTHON_CMD}). Python 3.9 이상을 설치해주세요.`));
      } else {
        reject(err);
      }
    });
  });
}
