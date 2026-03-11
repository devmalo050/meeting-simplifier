// scripts/setup.js — cross-platform setup wrapper
import { execFileSync } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

if (process.platform === 'win32') {
  try {
    execFileSync('powershell', ['-ExecutionPolicy', 'Bypass', '-File', path.join(__dirname, 'setup.ps1')], { stdio: 'inherit' });
  } catch (err) {
    process.exit(0); // Don't block session on setup failure
  }
} else {
  try {
    execFileSync('bash', [path.join(__dirname, 'setup.sh')], { stdio: 'inherit' });
  } catch (err) {
    process.exit(0); // Don't block session on setup failure
  }
}
