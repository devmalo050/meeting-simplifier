// mcp-server/index.js
import http from 'http';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { z } from 'zod';
import { startRecording, stopRecording, cleanupTempFiles } from './recorder.js';
import { transcribeAudio } from './transcriber.js';
import { saveMeeting } from './exporter.js';

const PORT = 43842;

function createMcpServer() {
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
    description: '오디오 파일을 텍스트로 변환합니다 (Whisper large-v3).',
    inputSchema: {
      audio_path: z.string().describe('변환할 오디오 파일 경로 (WAV/MP3/M4A)'),
    },
  }, async ({ audio_path }) => {
    try {
      const result = await transcribeAudio(audio_path, (current, total) => {
        process.stderr.write(`변환 중... ${current}/${total} 청크 완료\n`);
      });
      return { content: [{ type: 'text', text: JSON.stringify(result) }] };
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

  return server;
}

const httpServer = http.createServer(async (req, res) => {
  const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
  const mcpServer = createMcpServer();
  await mcpServer.connect(transport);
  await transport.handleRequest(req, res);
});

httpServer.listen(PORT, '127.0.0.1', () => {
  process.stderr.write(`meeting-simplifier MCP server listening on http://127.0.0.1:${PORT}\n`);
});

process.on('SIGINT', () => { cleanupTempFiles(); process.exit(0); });
process.on('SIGTERM', () => { cleanupTempFiles(); process.exit(0); });
