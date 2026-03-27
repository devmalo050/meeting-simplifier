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
    fileStream.destroy();
    return { error: `녹음 시작 실패: ${err.message}\nsox/rec가 설치되어 있는지 확인하세요.` };
  }

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

  // fileStream 에러 처리 — 디스크 쓰기 실패 시 cleanup
  fileStream.on('error', (err) => {
    console.error(`파일 쓰기 실패: ${err.message}`);
    cleanupTempFiles();
  });

  recording.stream().pipe(fileStream);

  activeRecording = { recording, tempPath, fileStream, startedAt: Date.now() };
  return { ok: true };
}

export function stopRecording() {
  if (!activeRecording) {
    return Promise.resolve({ error: '진행 중인 녹음이 없습니다.' });
  }

  const { recording, tempPath, fileStream, startedAt } = activeRecording;
  const duration = Math.round((Date.now() - startedAt) / 1000);

  try { recording.stop(); } catch {}

  // fileStream 'finish' 이벤트로 파일 플러시 완료 감지 (폴링 불필요)
  return new Promise((resolve) => {
    fileStream.once('finish', () => {
      activeRecording = null;
      try {
        const size = fs.statSync(tempPath).size;
        resolve(size > 0
          ? { audio_path: tempPath, duration_seconds: duration }
          : { error: '녹음 파일이 비어있습니다.' });
      } catch {
        resolve({ error: '녹음 파일을 찾을 수 없습니다.' });
      }
    });

    fileStream.once('error', (err) => {
      activeRecording = null;
      resolve({ error: `파일 쓰기 실패: ${err.message}` });
    });

    try { fileStream.end(); } catch {}
  });
}

export function cleanupTempFiles() {
  if (!activeRecording) return;
  try { activeRecording.recording.stop(); } catch {}
  try { activeRecording.fileStream.destroy(); } catch {}
  try { fs.unlinkSync(activeRecording.tempPath); } catch {}
  activeRecording = null;
}
