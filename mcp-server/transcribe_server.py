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
            return f.getnframes() / f.getframerate()
    except Exception:
        return 0

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
