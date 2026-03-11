# scripts/setup.ps1 — faster-whisper 자동 설치 (Windows)

$pythonCmd = $null

foreach ($cmd in @("python", "python3")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        $pythonCmd = $cmd
        break
    }
}

if (-not $pythonCmd) {
    Write-Host "⚠️  [meeting-simplifier] Python이 설치되어 있지 않습니다."
    Write-Host "   회의 녹음은 가능하지만, 음성 변환 및 회의록 생성이 작동하지 않습니다."
    Write-Host "   Python 3.9 이상이 필요합니다: https://python.org/downloads"
    Write-Host "   Python 설치 후 Claude를 재시작하면 자동으로 설정됩니다."
    exit 0
}

# Python 버전 확인 (3.9 이상 필요)
$pyVersion = & $pythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$pyMajor = & $pythonCmd -c "import sys; print(sys.version_info.major)"
$pyMinor = & $pythonCmd -c "import sys; print(sys.version_info.minor)"

if ([int]$pyMajor -lt 3 -or ([int]$pyMajor -eq 3 -and [int]$pyMinor -lt 9)) {
    Write-Host "⚠️  [meeting-simplifier] Python $pyVersion 이 감지되었지만 3.9 이상이 필요합니다."
    Write-Host "   https://python.org/downloads 에서 최신 버전을 설치해주세요."
    exit 0
}

$installed = & $pythonCmd -c "import faster_whisper" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "📦 faster-whisper를 설치합니다..."
    & $pythonCmd -m pip install faster-whisper --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ faster-whisper 설치 실패. 수동으로 실행하세요: pip install faster-whisper"
    } else {
        Write-Host "✅ faster-whisper 설치 완료"
    }
}
