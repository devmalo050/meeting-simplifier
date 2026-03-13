// mcp-server/recorder.js
import recorder from 'node-record-lpcm16';
import fs from 'fs';
import path from 'path';
import os from 'os';

const STATE_FILE = path.join(os.tmpdir(), 'meeting-simplifier-state.json');

function readState() {
  try {
    return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
  } catch {
    return null;
  }
}

function writeState(state) {
  fs.writeFileSync(STATE_FILE, JSON.stringify(state), 'utf8');
}

function clearState() {
  try { fs.unlinkSync(STATE_FILE); } catch {}
}

// 프로세스별 인메모리 recording 핸들 (파일로 공유 불가한 부분)
let activeRecording = null;

export function startRecording() {
  if (readState()) {
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
    cleanupTempFiles();
  });

  activeRecording = { recording, tempPath, fileStream };
  writeState({ tempPath, pid: process.pid });
  return { ok: true };
}

export function stopRecording() {
  const state = readState();

  if (!state) {
    return Promise.resolve({ error: '진행 중인 녹음이 없습니다.' });
  }

  const { tempPath, pid } = state;

  // 같은 프로세스에서 녹음 중인 경우 — 정상 종료
  if (activeRecording && pid === process.pid) {
    const { recording, fileStream } = activeRecording;

    return new Promise((resolve) => {
      fileStream.on('finish', () => {
        activeRecording = null;
        clearState();
        resolve({ audio_path: tempPath });
      });
      recording.stop();
      recording.stream().once('end', () => fileStream.end());
    });
  }

  // 다른 프로세스에서 녹음 중인 경우 — 해당 프로세스에 SIGTERM 보내고 파일 대기
  clearState();
  try { process.kill(pid, 'SIGTERM'); } catch {}

  // 파일이 완성될 때까지 최대 3초 대기
  return new Promise((resolve) => {
    let waited = 0;
    const interval = setInterval(() => {
      waited += 200;
      const exists = fs.existsSync(tempPath) && fs.statSync(tempPath).size > 0;
      if (exists || waited >= 3000) {
        clearInterval(interval);
        resolve(exists ? { audio_path: tempPath } : { error: '녹음 파일을 찾을 수 없습니다.' });
      }
    }, 200);
  });
}

export function cleanupTempFiles() {
  const state = readState();
  if (activeRecording) {
    try { activeRecording.recording.stop(); } catch {}
    try { fs.unlinkSync(activeRecording.tempPath); } catch {}
    activeRecording = null;
  }
  if (state) {
    try { fs.unlinkSync(state.tempPath); } catch {}
    clearState();
  }
}
