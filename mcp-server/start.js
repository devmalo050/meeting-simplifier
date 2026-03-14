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

// setup.sh로 전체 환경 설치 (sox, npm, venv, faster-whisper, 모델)
// venv 또는 Whisper 모델이 없으면 setup.sh 실행
const venvPython = process.platform === 'win32'
  ? path.join(pluginRoot, '.venv', 'Scripts', 'python.exe')
  : path.join(pluginRoot, '.venv', 'bin', 'python');
const modelCache = path.join(os.homedir(), '.cache', 'huggingface', 'hub', `models--Systran--faster-whisper-${WHISPER_MODEL}`);

const needsSetup = !existsSync(venvPython) || !existsSync(modelCache);

if (needsSetup) {
  try {
    execFileSync('bash', [path.join(pluginRoot, 'scripts', 'setup.sh')], {
      cwd: pluginRoot,
      env: { ...process.env, WHISPER_MODEL },
      stdio: ['ignore', 'inherit', 'inherit'],
      timeout: 600000,
    });
  } catch (e) {
    process.stderr.write(`[meeting-simplifier] setup 실패: ${e.message}\n`);
  }
}

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

// index.js를 자식 프로세스로 실행, stdio 그대로 전달 (WHISPER_MODEL 환경변수 전달)
const child = spawn(process.execPath, [path.join(__dirname, 'index.js')], {
  stdio: 'inherit',
  cwd: pluginRoot,
  env: { ...process.env, WHISPER_MODEL },
});

child.on('exit', (code) => process.exit(code ?? 0));
