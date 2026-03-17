# scripts/setup.ps1 — sox, faster-whisper(venv), Whisper 모델 자동 설치 (Windows)

$pluginRoot = Split-Path -Parent $PSScriptRoot

# ── 중복 실행 방지 ──────────────────────────────────────────────────────────
$lockFile = Join-Path $env:TEMP "meeting-simplifier-setup.lock"
if (Test-Path $lockFile) { exit 0 }
New-Item -ItemType File -Path $lockFile -Force | Out-Null

function Cleanup { Remove-Item -Path $lockFile -Force -ErrorAction SilentlyContinue }
trap { Cleanup; break }

# ── 1. SoX 설치 (녹음에 필요) ──────────────────────────────────────────────
if (-not (Get-Command sox -ErrorAction SilentlyContinue)) {
    if (Get-Command choco -ErrorAction SilentlyContinue) {
        Write-Host "SoX를 설치합니다 (choco install sox)..."
        choco install sox --yes --quiet 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "SoX 설치 완료"
        } else {
            Write-Host "SoX 설치 실패. 수동으로 설치하세요: https://sourceforge.net/projects/sox/"
        }
    } else {
        Write-Host "SoX가 없습니다. 녹음 기능이 작동하지 않습니다."
        Write-Host "설치 방법: https://sourceforge.net/projects/sox/ 또는 choco install sox"
    }
}

# ── 2. Python 확인 ─────────────────────────────────────────────────────────
$pythonCmd = $null
foreach ($cmd in @("python", "python3")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        $pythonCmd = $cmd
        break
    }
}

if (-not $pythonCmd) {
    Write-Host "[meeting-simplifier] Python이 설치되어 있지 않습니다."
    Write-Host "음성 변환 기능이 작동하지 않습니다. Python 3.9 이상 필요: https://python.org/downloads"
    Cleanup; exit 0
}

$pyMajor = [int](& $pythonCmd -c "import sys; print(sys.version_info.major)")
$pyMinor = [int](& $pythonCmd -c "import sys; print(sys.version_info.minor)")
if ($pyMajor -lt 3 -or ($pyMajor -eq 3 -and $pyMinor -lt 9)) {
    Write-Host "[meeting-simplifier] Python $pyMajor.$pyMinor 감지 — 3.9 이상이 필요합니다."
    Cleanup; exit 0
}

# ── Whisper 모델 설정 (start.js에서 WHISPER_MODEL 환경변수로 전달, 없으면 medium) ──
$whisperModel = if ($env:WHISPER_MODEL) { $env:WHISPER_MODEL } else { "medium" }

# ── 3. venv 생성 및 faster-whisper 설치 ────────────────────────────────────
$venvDir = Join-Path $pluginRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Python 가상환경을 생성합니다..."
    & $pythonCmd -m venv $venvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "venv 생성 실패"
        Cleanup; exit 0
    }
    Write-Host "가상환경 생성 완료"
}

& $venvPython -c "import faster_whisper" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "faster-whisper를 설치합니다..."
    & $venvPython -m pip install faster-whisper --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Host "faster-whisper 설치 실패. 수동으로 실행하세요: pip install faster-whisper"
    } else {
        Write-Host "faster-whisper 설치 완료"
    }
}

# ── 4. Whisper 모델 미리 다운로드 ─────────────────────────────────────────
$modelCache = Join-Path $env:USERPROFILE ".cache\huggingface\hub\models--Systran--faster-whisper-$whisperModel"
if (-not (Test-Path $modelCache)) {
    Write-Host "Whisper $whisperModel 모델을 다운로드합니다 (최초 1회)..."
    & $venvPython -c "from faster_whisper import WhisperModel; WhisperModel('$whisperModel', device='cpu', compute_type='int8')" 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Whisper $whisperModel 모델 준비 완료"
    } else {
        Write-Host "모델 다운로드 실패 (첫 번째 변환 시 자동 다운로드됩니다)"
    }
}

Cleanup
