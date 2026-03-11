// mcp-server/recorder.js
import recorder from 'node-record-lpcm16';
import fs from 'fs';
import path from 'path';
import os from 'os';

let activeRecording = null; // { recording, tempPath, fileStream }

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
    cleanupTempFiles();
  });

  activeRecording = { recording, tempPath, fileStream };
  return { ok: true };
}

export function stopRecording() {
  if (!activeRecording) {
    return Promise.resolve({ error: '진행 중인 녹음이 없습니다.' });
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
