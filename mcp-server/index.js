// mcp-server/index.js
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { startRecording, stopRecording, cleanupTempFiles } from './recorder.js';
import { transcribeAudio } from './transcriber.js';
import { saveMeeting } from './exporter.js';

const server = new Server(
  { name: 'meeting-simplifier', version: '1.0.0' },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: 'meeting_record_start',
      description: '마이크 녹음을 시작합니다.',
      inputSchema: { type: 'object', properties: {} },
    },
    {
      name: 'meeting_record_stop',
      description: '녹음을 중지하고 WAV 파일 경로를 반환합니다.',
      inputSchema: { type: 'object', properties: {} },
    },
    {
      name: 'meeting_transcribe',
      description: '오디오 파일을 텍스트로 변환합니다 (Whisper large-v3).',
      inputSchema: {
        type: 'object',
        properties: {
          audio_path: { type: 'string', description: '변환할 오디오 파일 경로 (WAV/MP3/M4A)' },
        },
        required: ['audio_path'],
      },
    },
    {
      name: 'meeting_save',
      description: '회의록과 녹음 파일을 지정 디렉토리에 저장합니다.',
      inputSchema: {
        type: 'object',
        properties: {
          title: { type: 'string', description: '회의 제목 (디렉토리명에 사용)' },
          transcript: { type: 'string', description: 'Whisper 원문 트랜스크립트' },
          minutes: { type: 'string', description: '회의록 본문 (마크다운)' },
          audio_path: { type: 'string', description: '저장할 녹음 파일 경로' },
          format: { type: 'string', enum: ['md', 'txt', 'docx'], description: '출력 포맷' },
          output_dir: { type: 'string', description: '저장 기본 디렉토리' },
        },
        required: ['title', 'transcript', 'minutes', 'audio_path', 'format', 'output_dir'],
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    if (name === 'meeting_record_start') {
      const result = startRecording();
      return { content: [{ type: 'text', text: JSON.stringify(result) }] };
    }

    if (name === 'meeting_record_stop') {
      const result = await stopRecording();
      return { content: [{ type: 'text', text: JSON.stringify(result) }] };
    }

    if (name === 'meeting_transcribe') {
      const { audio_path } = args;
      const result = await transcribeAudio(audio_path, (current, total) => {
        process.stderr.write(`변환 중... ${current}/${total} 청크 완료\n`);
      });
      return { content: [{ type: 'text', text: JSON.stringify(result) }] };
    }

    if (name === 'meeting_save') {
      const { title, transcript, minutes, audio_path, format, output_dir } = args;
      // Remap snake_case MCP args to camelCase saveMeeting params
      const result = await saveMeeting({
        title,
        transcript,
        minutes,
        audioPath: audio_path,
        format,
        outputDir: output_dir,
      });
      return { content: [{ type: 'text', text: JSON.stringify(result) }] };
    }

    return {
      content: [{ type: 'text', text: JSON.stringify({ error: `알 수 없는 도구: ${name}` }) }],
    };
  } catch (err) {
    return { content: [{ type: 'text', text: JSON.stringify({ error: err.message }) }] };
  }
});

// Clean up temp files on process exit
process.on('SIGINT', () => { cleanupTempFiles(); process.exit(0); });
process.on('SIGTERM', () => { cleanupTempFiles(); process.exit(0); });

const transport = new StdioServerTransport();
await server.connect(transport);
