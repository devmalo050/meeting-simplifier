# mcp-server/transcribe.py
import sys
import json
import os
import wave
import tempfile
from faster_whisper import WhisperModel

CHUNK_SECS = 600   # 10 minutes
OVERLAP_SECS = 30  # 30 second overlap
SAMPLE_RATE = 16000

def read_wav_duration(path):
    try:
        with wave.open(path, 'r') as f:
            return f.getnframes() / f.getframerate()
    except Exception:
        return 0

def split_wav(path, chunk_secs, overlap_secs):
    """Split WAV file into chunks, return list of temp file paths."""
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

def transcribe(audio_path):
    model = WhisperModel("large-v3", device="auto", compute_type="auto")

    duration = read_wav_duration(audio_path)
    # Chunk splitting only for WAV files (MP3/M4A handled internally by faster-whisper)
    is_long = duration > CHUNK_SECS and audio_path.lower().endswith('.wav')

    if is_long:
        chunk_paths = split_wav(audio_path, CHUNK_SECS, OVERLAP_SECS)
        total = len(chunk_paths)
        all_text = []
        detected_language = 'ko'

        for i, chunk_path in enumerate(chunk_paths, 1):
            print(f"PROGRESS:{i}/{total}", file=sys.stderr, flush=True)
            segments, info = model.transcribe(chunk_path, language=None, beam_size=5)
            text = " ".join(s.text.strip() for s in segments)
            all_text.append(text)
            detected_language = info.language
            os.unlink(chunk_path)

        transcript = " ".join(all_text)
        language = detected_language
    else:
        segments, info = model.transcribe(audio_path, language=None, beam_size=5)
        transcript = " ".join(s.text.strip() for s in segments)
        language = info.language

    print(json.dumps({"transcript": transcript, "language": language}, ensure_ascii=False))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "audio_path argument required"}))
        sys.exit(1)
    audio_path = sys.argv[1]
    transcribe(audio_path)
