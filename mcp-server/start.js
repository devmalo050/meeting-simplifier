#!/usr/bin/env node
// mcp-server/start.js — 환경 자동 설치(node_modules + Python venv) 후 MCP 서버 시작
import { execFileSync, spawn } from 'child_process';
import { existsSync } from 'fs';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const pluginRoot = path.join(__dirname, '..');

// setup.sh로 전체 환경 설치 (sox, npm, venv, faster-whisper)
// .venv가 없으면 초기 설치, 있으면 skip
const venvPython = process.platform === 'win32'
  ? path.join(pluginRoot, '.venv', 'Scripts', 'python.exe')
  : path.join(pluginRoot, '.venv', 'bin', 'python');

if (!existsSync(venvPython)) {
  const setupScript = path.join(pluginRoot, 'scripts', 'setup.sh');
  if (existsSync(setupScript)) {
    try {
      execFileSync('bash', [setupScript], {
        cwd: pluginRoot,
        stdio: ['ignore', 'inherit', 'inherit'],
        timeout: 600000,
      });
    } catch (e) {
      process.stderr.write(`[meeting-simplifier] setup 실패: ${e.message}\n`);
    }
  } else {
    // setup.sh 없으면 npm install만 fallback
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
  }
} else if (!existsSync(path.join(pluginRoot, 'node_modules', '@modelcontextprotocol'))) {
  // venv는 있지만 node_modules가 없는 경우
  try {
    execFileSync('npm', ['install', '--prefer-offline', '--quiet'], {
      cwd: pluginRoot,
      stdio: ['ignore', 'ignore', 'inherit'],
    });
  } catch (e) {
    process.stderr.write(`[meeting-simplifier] npm install 실패: ${e.message}\n`);
  }
}

// index.js를 자식 프로세스로 실행, stdio 그대로 전달
const child = spawn(process.execPath, [path.join(__dirname, 'index.js')], {
  stdio: 'inherit',
  cwd: pluginRoot,
});

child.on('exit', (code) => process.exit(code ?? 0));
