#!/usr/bin/env node
// mcp-server/start.js — 환경 자동 설치(node_modules + Python venv) 후 MCP 서버 시작
import { execFileSync, spawn } from 'child_process';
import { existsSync } from 'fs';
import { fileURLToPath } from 'url';
import os from 'os';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const pluginRoot = path.join(__dirname, '..');

// ── 기존 start.js 인스턴스 종료 (중복 실행 방지) ────────────────────────────
// start.js 프로세스만 타겟 — SIGTERM 포워딩으로 자식 index.js도 같이 종료됨
import { spawnSync } from 'child_process';
try {
  if (process.platform === 'win32') {
    const result = spawnSync('wmic', ['process', 'where', 'name="node.exe"', 'get', 'ProcessId,CommandLine', '/format:csv'], { encoding: 'utf8' });
    for (const line of result.stdout.split('\n')) {
      if (!line.includes('start.js') || !line.includes('meeting-simplifier')) continue;
      const match = line.match(/,(\d+)\s*$/);
      if (!match) continue;
      const pid = parseInt(match[1], 10);
      if (!pid || pid === process.pid) continue;
      spawnSync('taskkill', ['/PID', String(pid), '/F'], { encoding: 'utf8' });
    }
  } else {
    const result = spawnSync('pgrep', ['-f', 'mcp-server/start.js'], { encoding: 'utf8' });
    for (const pidStr of result.stdout.trim().split('\n').filter(Boolean)) {
      const pid = parseInt(pidStr, 10);
      if (!pid || pid === process.pid) continue;
      try { process.kill(pid, 'SIGTERM'); } catch {}
    }
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
// Windows는 %USERPROFILE%\.cache, macOS/Linux는 ~/.cache
const modelCache = path.join(os.homedir(), '.cache', 'huggingface', 'hub', `models--Systran--faster-whisper-${WHISPER_MODEL}`);

if (!existsSync(venvPython) || !existsSync(modelCache)) {
  const setupProc = process.platform === 'win32'
    ? spawn('powershell', ['-ExecutionPolicy', 'Bypass', '-File', path.join(pluginRoot, 'scripts', 'setup.ps1')], {
        cwd: pluginRoot,
        env: { ...process.env, WHISPER_MODEL },
        stdio: 'ignore',
        detached: true,
      })
    : spawn('bash', [path.join(pluginRoot, 'scripts', 'setup.sh')], {
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
