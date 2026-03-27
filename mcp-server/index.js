// mcp-server/index.js
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { execFileSync, spawn } from 'child_process';
import { existsSync, readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import path from 'path';
import os from 'os';
import { startRecording, stopRecording, cleanupTempFiles, getLastAudioPath } from './recorder.js';
import { transcribeAudio, killActiveTranscription, warmupWorker } from './transcriber.js';
import { saveMeeting } from './exporter.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PLUGIN_ROOT = path.join(__dirname, '..');

const WHISPER_MODEL = process.env.WHISPER_MODEL ?? 'medium';

// npm install — MCP 서버 구동에 필수
if (!existsSync(path.join(PLUGIN_ROOT, 'node_modules', '@modelcontextprotocol'))) {
  try {
    execFileSync('npm', ['install', '--prefer-offline', '--quiet'], {
      cwd: PLUGIN_ROOT,
      stdio: ['ignore', 'ignore', 'inherit'],
    });
  } catch (e) {
    process.stderr.write(`[meeting-simplifier] npm install 실패: ${e.message}\n`);
  }
}

// setup.sh — venv/모델 설치, 백그라운드 실행
const venvPython = process.platform === 'win32'
  ? path.join(PLUGIN_ROOT, '.venv', 'Scripts', 'python.exe')
  : path.join(PLUGIN_ROOT, '.venv', 'bin', 'python');
const modelCache = path.join(os.homedir(), '.cache', 'huggingface', 'hub', `models--Systran--faster-whisper-${WHISPER_MODEL}`);

if (!existsSync(venvPython) || !existsSync(modelCache)) {
  const setupProc = process.platform === 'win32'
    ? spawn('powershell', ['-ExecutionPolicy', 'Bypass', '-File', path.join(PLUGIN_ROOT, 'scripts', 'setup.ps1')], {
        cwd: PLUGIN_ROOT, env: { ...process.env, WHISPER_MODEL }, stdio: 'ignore', detached: true,
      })
    : spawn('bash', [path.join(PLUGIN_ROOT, 'scripts', 'setup.sh')], {
        cwd: PLUGIN_ROOT, env: { ...process.env, WHISPER_MODEL }, stdio: 'ignore', detached: true,
      });
  setupProc.unref();
}

function readSettings() {
  try {
    const raw = readFileSync(path.join(PLUGIN_ROOT, 'settings.json'), 'utf-8');
    return JSON.parse(raw)['meeting-simplifier'] ?? {};
  } catch {
    return {};
  }
}

const server = new McpServer({ name: 'meeting-simplifier', version: '1.0.0' });

server.registerTool('meeting_record_start', {
  description: '마이크 녹음을 시작합니다.',
  inputSchema: {},
}, async () => {
  const result = startRecording();
  return { content: [{ type: 'text', text: JSON.stringify(result) }] };
});

server.registerTool('meeting_record_stop', {
  description: '녹음을 중지하고 WAV 파일 경로와 녹음 시간을 반환합니다.',
  inputSchema: {},
}, async () => {
  const t = Date.now();
  const result = await stopRecording();
  result.stop_elapsed_seconds = ((Date.now() - t) / 1000).toFixed(1);
  return { content: [{ type: 'text', text: JSON.stringify(result) }] };
});

server.registerTool('meeting_transcribe', {
  description: '오디오 파일을 텍스트로 변환합니다.',
  inputSchema: {
    audio_path: z.string().describe('변환할 오디오 파일 경로 (WAV/MP3/M4A)'),
  },
}, async ({ audio_path }) => {
  // venv 준비 중 여부 확인 (설치/재설치 직후)
  const venvPython = process.platform === 'win32'
    ? path.join(PLUGIN_ROOT, '.venv', 'Scripts', 'python.exe')
    : path.join(PLUGIN_ROOT, '.venv', 'bin', 'python');
  if (!existsSync(venvPython)) {
    return { content: [{ type: 'text', text: JSON.stringify({ error: '환경 설치가 아직 진행 중입니다. 1~2분 후 다시 시도해주세요.' }) }] };
  }
  try {
    const startTime = Date.now();
    const settings = readSettings();
    const output_language = settings.output_language ?? 'auto';
    const result = await transcribeAudio(audio_path, (current, total) => {
      process.stderr.write(`변환 중... ${current}/${total} 청크 완료\n`);
    }); // output_language는 회의록 작성 언어 설정 — Whisper 음성 인식 언어와 별개이므로 전달하지 않음
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    process.stderr.write(`변환 완료 (${elapsed}초)\n`);
    return { content: [{ type: 'text', text: JSON.stringify({ ...result, elapsed_seconds: parseFloat(elapsed), output_language }) }] };
  } catch (err) {
    return { content: [{ type: 'text', text: JSON.stringify({ error: err.message }) }] };
  }
});

server.registerTool('meeting_save', {
  description: '회의록과 녹음 파일을 지정 디렉토리에 저장합니다.',
  inputSchema: {
    title: z.string().describe('회의 제목 (디렉토리명에 사용)'),
    transcript: z.string().describe('Whisper 원문 트랜스크립트'),
    minutes: z.string().describe('회의록 본문 (마크다운)'),
    audio_path: z.string().describe('저장할 녹음 파일 경로'),
    format: z.enum(['md', 'txt', 'docx']).optional().describe('출력 포맷 (없으면 settings.json 값 사용)'),
    output_dir: z.string().optional().describe('저장 기본 디렉토리 (없으면 settings.json 값 사용)'),
  },
}, async ({ title, transcript, minutes, audio_path, format, output_dir }) => {
  const settings = readSettings();
  const resolvedFormat = format ?? settings.output_format ?? 'md';
  const resolvedOutputDir = output_dir ?? settings.output_dir ?? '~/Documents/meetings';
  // audio_path가 비어있으면 텍스트 전용 (summarize skill) — fallback 없이 그대로 사용
  // audio_path가 있는데 파일이 없으면 마지막 녹음 파일로 fallback (stop skill 이상 상태 대비)
  let resolvedAudioPath = audio_path || '';
  if (resolvedAudioPath && !existsSync(resolvedAudioPath)) {
    const last = getLastAudioPath();
    if (last && existsSync(last)) {
      process.stderr.write(`[meeting-save] audio_path 불일치 감지, 마지막 녹음 파일 사용: ${last}\n`);
      resolvedAudioPath = last;
    }
  }
  try {
    const result = await saveMeeting({
      title, transcript, minutes,
      audioPath: resolvedAudioPath,
      format: resolvedFormat,
      outputDir: resolvedOutputDir,
    });
    const settings2 = readSettings();
    return { content: [{ type: 'text', text: JSON.stringify({ ...result, output_language: settings2.output_language ?? 'auto' }) }] };
  } catch (err) {
    return { content: [{ type: 'text', text: JSON.stringify({ error: err.message }) }] };
  }
});

process.on('SIGINT', () => { killActiveTranscription(); cleanupTempFiles(); process.exit(0); });
process.on('SIGTERM', () => { killActiveTranscription(); cleanupTempFiles(); process.exit(0); });

const transport = new StdioServerTransport();
await server.connect(transport);

// MCP 서버 시작 직후 Whisper 모델을 백그라운드에서 미리 로딩 (첫 변환 지연 제거)
warmupWorker();
