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
        if (!result.transcript) {
          resolve({ transcript: '', language: 'ko', empty: true });
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
