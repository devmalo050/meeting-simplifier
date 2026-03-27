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
