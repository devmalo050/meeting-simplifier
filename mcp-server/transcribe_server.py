# mcp-server/transcribe_server.py
# 상주 프로세스: 모델을 한 번 로드하고 stdin에서 요청을 받아 처리
import sys
import json
import os
import wave
import tempfile
from faster_whisper import WhisperModel

CHUNK_SECS = 600
OVERLAP_SECS = 30

def read_wav_duration(path):
    try:
        with wave.open(path, 'r') as f:
            params = f.getparams()
            # node-record-lpcm16은 WAV 헤더의 nframes를 올바르게 기록하지 않음
            # 실제 파일 크기로 프레임 수를 계산
            file_size = os.path.getsize(path)
            header_size = 44
            actual_frames = (file_size - header_size) // (params.nchannels * params.sampwidth)
            return actual_frames / params.framerate
    except Exception:
        return 0


def fix_wav_header(path):
    """WAV 헤더의 nframes가 잘못된 경우 수정된 임시 파일 반환. 정상이면 원본 경로 반환."""
    try:
        with wave.open(path, 'r') as f:
            params = f.getparams()
            file_size = os.path.getsize(path)
            header_size = 44
            actual_frames = (file_size - header_size) // (params.nchannels * params.sampwidth)
            if abs(params.nframes - actual_frames) <= 160:  # 10ms 이내 오차는 정상
                return path, False
            # 헤더 불일치 — 실제 데이터로 새 WAV 파일 생성
            f.rewind()
            raw = f.readframes(actual_frames)  # 헤더가 아닌 실제 프레임 수만큼 읽기
    except Exception:
        return path, False

    tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    with wave.open(tmp.name, 'w') as out:
        out.setparams(params._replace(nframes=actual_frames))
        out.writeframes(raw[:actual_frames * params.nchannels * params.sampwidth])
    return tmp.name, True

def split_wav(path, chunk_secs, overlap_secs):
    with wave.open(path, 'r') as f:
        params = f.getparams()
        frame_rate = f.getframerate()
        total_frames = f.getnframes()
        chunk_frames = int(chunk_secs * frame_rate)
        overlap_frames = int(overlap_secs * frame_rate)
        step_frames = chunk_frames - overlap_frames

        chunks = []
        offset = 0
        while offset < total_frames:
            end = min(offset + chunk_frames, total_frames)
            f.setpos(offset)
            frames = f.readframes(end - offset)
            tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            with wave.open(tmp.name, 'w') as out:
                out.setparams(params)
                out.writeframes(frames)
            chunks.append(tmp.name)
            offset += step_frames
    return chunks

def transcribe(model, audio_path):
    # WAV 헤더 nframes 오류 수정 (node-record-lpcm16 버그 대응)
    fixed_path, was_fixed = fix_wav_header(audio_path) if audio_path.lower().endswith('.wav') else (audio_path, False)
    if was_fixed:
        print(f"WAV 헤더 수정됨: {audio_path}", file=sys.stderr, flush=True)
    try:
        return _transcribe(model, fixed_path)
    finally:
        if was_fixed and os.path.exists(fixed_path):
            os.unlink(fixed_path)


def _transcribe(model, audio_path):
    duration = read_wav_duration(audio_path)
    is_long = duration > CHUNK_SECS and audio_path.lower().endswith('.wav')

    if is_long:
        chunk_paths = split_wav(audio_path, CHUNK_SECS, OVERLAP_SECS)
        total = len(chunk_paths)
        all_text = []
        language = None
        try:
            for i, chunk_path in enumerate(chunk_paths, 1):
                print(f"PROGRESS:{i}/{total}", file=sys.stderr, flush=True)
                segments, info = model.transcribe(chunk_path, language=None, beam_size=1)
                text = " ".join(s.text.strip() for s in segments)
                all_text.append(text)
                if language is None:
                    language = info.language
                os.unlink(chunk_path)
        except Exception:
            for p in chunk_paths:
                if os.path.exists(p):
                    try: os.unlink(p)
                    except: pass
            raise
        transcript = " ".join(all_text)
    else:
        segments, info = model.transcribe(audio_path, language=None, beam_size=1)
        transcript = " ".join(s.text.strip() for s in segments)
        language = info.language

    return {"transcript": transcript, "language": language}

def main():
    whisper_model = os.environ.get("WHISPER_MODEL", "small")
    print(f"READY:loading model={whisper_model}", file=sys.stderr, flush=True)
    model = WhisperModel(whisper_model, device="cpu", compute_type="int8")
    print("READY:ok", file=sys.stderr, flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            audio_path = req.get("audio_path", "")
            if not audio_path:
                print(json.dumps({"error": "audio_path required"}), flush=True)
                continue
            result = transcribe(model, audio_path)
            print(json.dumps(result, ensure_ascii=False), flush=True)
        except Exception as e:
            print(json.dumps({"error": str(e)}, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
