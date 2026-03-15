#!/usr/bin/env node
// mcp-server/start.js — 환경 자동 설치(node_modules + Python venv) 후 MCP 서버 시작
import { execFileSync, spawnSync, spawn } from 'child_process';
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

// index.js를 spawnSync로 실행 — 현재 프로세스가 끝날 때까지 블로킹
// spawn 대신 spawnSync를 쓰면 start.js 프로세스가 index.js와 1:1로 대응되어
// reload 시 중복 프로세스가 생기지 않음
const result = spawnSync(process.execPath, [path.join(__dirname, 'index.js')], {
  cwd: pluginRoot,
  env: { ...process.env, WHISPER_MODEL },
  stdio: 'inherit',
});

process.exit(result.status ?? 0);
