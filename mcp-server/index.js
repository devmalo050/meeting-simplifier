// mcp-server/index.js
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { existsSync } from 'fs';
import { fileURLToPath } from 'url';
import path from 'path';
import { startRecording, stopRecording, cleanupTempFiles } from './recorder.js';
import { transcribeAudio, killActiveTranscription } from './transcriber.js';
import { saveMeeting } from './exporter.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PLUGIN_ROOT = path.join(__dirname, '..');

const server = new McpServer({ name: 'meeting-simplifier', version: '1.0.0' });

server.registerTool('meeting_record_start', {
  description: '마이크 녹음을 시작합니다.',
  inputSchema: {},
}, async () => {
  const result = startRecording();
  return { content: [{ type: 'text', text: JSON.stringify(result) }] };
});

server.registerTool('meeting_record_stop', {
  description: '녹음을 중지하고 WAV 파일 경로를 반환합니다.',
  inputSchema: {},
}, async () => {
  const result = await stopRecording();
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
    const result = await transcribeAudio(audio_path, (current, total) => {
      process.stderr.write(`변환 중... ${current}/${total} 청크 완료\n`);
    });
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    process.stderr.write(`변환 완료 (${elapsed}초)\n`);
    return { content: [{ type: 'text', text: JSON.stringify({ ...result, elapsed_seconds: parseFloat(elapsed) }) }] };
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
    format: z.enum(['md', 'txt', 'docx']).describe('출력 포맷'),
    output_dir: z.string().describe('저장 기본 디렉토리'),
  },
}, async ({ title, transcript, minutes, audio_path, format, output_dir }) => {
  try {
    const result = await saveMeeting({
      title, transcript, minutes,
      audioPath: audio_path,
      format,
      outputDir: output_dir,
    });
    return { content: [{ type: 'text', text: JSON.stringify(result) }] };
  } catch (err) {
    return { content: [{ type: 'text', text: JSON.stringify({ error: err.message }) }] };
  }
});

process.on('SIGINT', () => { killActiveTranscription(); cleanupTempFiles(); process.exit(0); });
process.on('SIGTERM', () => { killActiveTranscription(); cleanupTempFiles(); process.exit(0); });

const transport = new StdioServerTransport();
await server.connect(transport);
