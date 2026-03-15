// mcp-server/recorder.js
import recorder from 'node-record-lpcm16';
import fs from 'fs';
import path from 'path';
import os from 'os';

const STATE_FILE = path.join(os.tmpdir(), 'meeting-simplifier-state.json');
const LAST_AUDIO_FILE = path.join(os.tmpdir(), 'meeting-simplifier-last-audio.json');

export function getLastAudioPath() {
  try {
    const d = JSON.parse(fs.readFileSync(LAST_AUDIO_FILE, 'utf8'));
    return d.audio_path || null;
  } catch { return null; }
}

function saveLastAudioPath(audioPath) {
  fs.writeFileSync(LAST_AUDIO_FILE, JSON.stringify({ audio_path: audioPath }), 'utf8');
}

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

// 인메모리 recording 핸들 (이 프로세스에서 start한 경우에만 유효)
let activeRecording = null;

// 서버 시작 시 이전 프로세스의 stale state 정리
// (reload 시 MCP 서버가 재시작되면 state 파일은 남지만 activeRecording은 사라짐)
{
  const stale = readState();
  if (stale && stale.serverPid !== process.pid) {
    if (stale.recPid) { try { process.kill(stale.recPid, 'SIGTERM'); } catch {} }
    clearState();
  }
}

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
      console.error(
        process.platform === 'darwin'
          ? '마이크 접근 권한이 없습니다. 시스템 환경설정 → 개인 정보 보호 → 마이크에서 터미널 권한을 허용해주세요.'
          : '마이크 접근 권한이 없습니다. 설정 → 개인 정보 → 마이크에서 앱 접근을 허용해주세요.'
      );
    }
    cleanupTempFiles();
  });

  // rec 프로세스 PID를 state에 저장 (cross-process stop에 사용)
  const recPid = recording.process?.pid ?? null;
  activeRecording = { recording, tempPath, fileStream };
  writeState({ tempPath, serverPid: process.pid, recPid, startedAt: Date.now() });
  return { ok: true };
}

export function stopRecording() {
  const state = readState();

  if (!state) {
    return Promise.resolve({ error: '진행 중인 녹음이 없습니다.' });
  }

  const { tempPath, serverPid, recPid, startedAt } = state;
  const duration = startedAt ? Math.round((Date.now() - startedAt) / 1000) : null;

  // 같은 프로세스에서 start한 경우 — 정상 종료
  if (activeRecording && serverPid === process.pid) {
    const { recording, fileStream } = activeRecording;

    return new Promise((resolve) => {
      const timeout = setTimeout(() => {
        activeRecording = null;
        clearState();
        saveLastAudioPath(tempPath);
        resolve({ audio_path: tempPath, duration_seconds: duration });
      }, 10000); // 10초 타임아웃

      fileStream.on('finish', () => {
        clearTimeout(timeout);
        activeRecording = null;
        clearState();
        saveLastAudioPath(tempPath);
        resolve({ audio_path: tempPath, duration_seconds: duration });
      });
      recording.stop();
      recording.stream().once('end', () => fileStream.end());
    });
  }

  // 다른 프로세스에서 start한 경우 — rec 프로세스만 종료하고 파일 확정 대기
  clearState();
  if (recPid) {
    try { process.kill(recPid, 'SIGTERM'); } catch {}
  }

  // 파일이 디스크에 플러시될 때까지 최대 5초 대기
  return new Promise((resolve) => {
    let waited = 0;
    const interval = setInterval(() => {
      waited += 200;
      try {
        const size = fs.existsSync(tempPath) ? fs.statSync(tempPath).size : 0;
        if (size > 0 || waited >= 5000) {
          clearInterval(interval);
          if (size > 0) saveLastAudioPath(tempPath);
          resolve(size > 0 ? { audio_path: tempPath, duration_seconds: duration } : { error: '녹음 파일을 찾을 수 없습니다.' });
        }
      } catch {
        clearInterval(interval);
        resolve({ error: '녹음 파일을 찾을 수 없습니다.' });
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
