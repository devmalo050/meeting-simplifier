#!/usr/bin/env node
// mcp-server/start.js — node_modules 자동 설치 후 MCP 서버 시작
import { execFileSync, spawn } from 'child_process';
import { existsSync } from 'fs';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const pluginRoot = path.join(__dirname, '..');

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

// index.js를 자식 프로세스로 실행, stdio 그대로 전달
const child = spawn(process.execPath, [path.join(__dirname, 'index.js')], {
  stdio: 'inherit',
  cwd: pluginRoot,
});

child.on('exit', (code) => process.exit(code ?? 0));
