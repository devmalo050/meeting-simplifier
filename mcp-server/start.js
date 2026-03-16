#!/usr/bin/env node
// mcp-server/start.js — 환경 자동 설치(node_modules + Python venv) 후 MCP 서버 시작
import { execFileSync, spawnSync, spawn } from 'child_process';
import { existsSync } from 'fs';
import { fileURLToPath } from 'url';
import os from 'os';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const pluginRoot = path.join(__dirname, '..');

// ── 이전 버전 MCP 프로세스 종료 ─────────────────────────────────────────────
// meeting-simplifier 관련 모든 node 프로세스를 찾아 현재 버전 경로가 아닌 것을 종료
try {
  const result = spawnSync('pgrep', ['-f', 'meeting-simplifier'], { encoding: 'utf8' });
  const pids = result.stdout.trim().split('\n').filter(Boolean);
  for (const pidStr of pids) {
    const pid = parseInt(pidStr, 10);
    if (!pid || pid === process.pid) continue;
    try {
      const cmdline = spawnSync('ps', ['-p', String(pid), '-o', 'args='], { encoding: 'utf8' }).stdout;
      // meeting-simplifier 관련이지만 현재 pluginRoot(버전 경로)가 아닌 것만 종료
      if (cmdline.includes('meeting-simplifier') && !cmdline.includes(pluginRoot)) {
        process.kill(pid, 'SIGTERM');
      }
    } catch {}
  }
} catch {}

// ── Whisper 설정 (여기서만 관리, setup.sh와 transcribe.py에 전달) ──
export const WHISPER_MODEL = 'medium';

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

// index.js를 자식 프로세스로 실행
// start.js가 SIGTERM/SIGINT 받으면 자식도 같이 종료 → 구버전 고아 방지
const child = spawn(process.execPath, [path.join(__dirname, 'index.js')], {
  cwd: pluginRoot,
  env: { ...process.env, WHISPER_MODEL },
  stdio: 'inherit',
});

function forwardSignal(sig) {
  try { child.kill(sig); } catch {}
}
process.on('SIGTERM', () => { forwardSignal('SIGTERM'); });
process.on('SIGINT', () => { forwardSignal('SIGINT'); });

child.on('exit', (code) => {
  process.exit(code ?? 0);
});
