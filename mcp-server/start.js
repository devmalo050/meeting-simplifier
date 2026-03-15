#!/usr/bin/env node
// mcp-server/start.js — 환경 자동 설치(node_modules + Python venv) 후 MCP 서버 시작
import { execFileSync, spawn } from 'child_process';
import { existsSync } from 'fs';
import { fileURLToPath } from 'url';
import os from 'os';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const pluginRoot = path.join(__dirname, '..');

// ── Whisper 모델 설정 (여기서만 관리, setup.sh와 transcribe.py에 전달) ──
export const WHISPER_MODEL = 'small';

// npm install — MCP 서버 구동에 필수, 동기 실행
if (!existsSync(path.join(pluginRoot, 'node_modules', '@modelcontextprotocol'))) {
  try {
    execFileSync('npm', ['install', '--prefer-offline', '--quiet'], {
      cwd: pluginRoot,
      stdio: ['ignore', 'ignore', 'inherit'],
    });
  } catch (e) {
    process.stderr.write(`[meeting-simplifier] npm install 실패: ${e.message}\n`);
  }
}

// setup.sh — venv/모델 설치, 오래 걸리므로 백그라운드 실행
// MCP 서버는 즉시 시작하고, 음성 변환 시점에 venv가 준비되어 있으면 됨
const venvPython = process.platform === 'win32'
  ? path.join(pluginRoot, '.venv', 'Scripts', 'python.exe')
  : path.join(pluginRoot, '.venv', 'bin', 'python');
const modelCache = path.join(os.homedir(), '.cache', 'huggingface', 'hub', `models--Systran--faster-whisper-${WHISPER_MODEL}`);

if (!existsSync(venvPython) || !existsSync(modelCache)) {
  const setupProc = spawn('bash', [path.join(pluginRoot, 'scripts', 'setup.sh')], {
    cwd: pluginRoot,
    env: { ...process.env, WHISPER_MODEL },
    stdio: 'ignore',
    detached: true,
  });
  setupProc.unref();
}

// index.js를 자식 프로세스로 실행, stdio 그대로 전달 (WHISPER_MODEL 환경변수 전달)
const child = spawn(process.execPath, [path.join(__dirname, 'index.js')], {
  stdio: 'inherit',
  cwd: pluginRoot,
  env: { ...process.env, WHISPER_MODEL },
});

child.on('exit', (code) => process.exit(code ?? 0));
