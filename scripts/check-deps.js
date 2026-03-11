// scripts/check-deps.js
import { execSync } from 'child_process';

const checks = [
  {
    name: 'sox/rec',
    command: 'rec --version',
    installHint: {
      darwin: 'brew install sox',
      win32: 'https://sourceforge.net/projects/sox/files/sox/ 에서 직접 설치 후 PATH 추가',
    },
  },
  {
    name: 'faster-whisper',
    command: 'python3 -c "import faster_whisper"',
    installHint: {
      darwin: 'pip install faster-whisper',
      win32: 'pip install faster-whisper',
    },
  },
];

let allOk = true;
for (const check of checks) {
  try {
    execSync(check.command, { stdio: 'ignore' });
    console.log(`✅ ${check.name}`);
  } catch {
    const hint = check.installHint[process.platform] ?? check.installHint['darwin'];
    console.error(`❌ ${check.name} 미설치\n   설치: ${hint}`);
    allOk = false;
  }
}

if (!allOk) process.exit(1);
console.log('\n모든 의존성이 설치되어 있습니다.');
