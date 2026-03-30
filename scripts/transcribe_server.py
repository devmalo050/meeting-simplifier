# scripts/transcribe_server.py
# --oneshot PATH: 단발성 변환 후 JSON 출력하고 종료 (bash skill에서 직접 호출)
# 인수 없음: stdin 루프 (하위 호환)
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
            # wave 모듈이 data 청크 위치를 파악한 후 tell()로 정확한 오프셋 획득
            # (LIST 메타데이터 청크 등으로 44바이트보다 클 수 있으므로 하드코딩 금지)
            f.rewind()
            data_offset = f.tell()
            file_size = os.path.getsize(path)
            frame_size = params.nchannels * params.sampwidth
            actual_frames = (file_size - data_offset) // frame_size
            if abs(params.nframes - actual_frames) <= 160:  # 10ms 이내 오차는 정상
                return path, False
            # 헤더 불일치 — raw binary로 직접 읽어야 wave 모듈의 nframes 제한을 우회
    except Exception:
        return path, False

    try:
        raw_size = actual_frames * params.nchannels * params.sampwidth
        with open(path, 'rb') as bf:
            bf.seek(data_offset)
            raw = bf.read(raw_size)
    except Exception:
        return path, False

    tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    with wave.open(tmp.name, 'w') as out:
        out.setparams(params._replace(nframes=actual_frames))
        out.writeframes(raw)
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

def transcribe(model, audio_path, language=None):
    # WAV 헤더 nframes 오류 수정 (node-record-lpcm16 버그 대응)
    fixed_path, was_fixed = fix_wav_header(audio_path) if audio_path.lower().endswith('.wav') else (audio_path, False)
    if was_fixed:
        print(f"WAV 헤더 수정됨: {audio_path}", file=sys.stderr, flush=True)
    try:
        return _transcribe(model, fixed_path, language=language)
    finally:
        if was_fixed and os.path.exists(fixed_path):
            os.unlink(fixed_path)


def _transcribe(model, audio_path, language=None):
    duration = read_wav_duration(audio_path)
    is_long = duration > CHUNK_SECS and audio_path.lower().endswith('.wav')

    # language가 None이거나 "auto"면 자동 감지, 그 외("ko", "en" 등)면 고정
    lang_param = None if (language is None or language == "auto") else language

    if is_long:
        chunk_paths = split_wav(audio_path, CHUNK_SECS, OVERLAP_SECS)
        total = len(chunk_paths)
        all_text = []
        detected_language = None
        try:
            for i, chunk_path in enumerate(chunk_paths, 1):
                print(f"PROGRESS:{i}/{total}", file=sys.stderr, flush=True)
                segments, info = model.transcribe(chunk_path, language=lang_param, beam_size=1, vad_filter=True)
                text = "\n".join(s.text.strip() for s in segments)
                all_text.append(text)
                if detected_language is None:
                    detected_language = info.language
                os.unlink(chunk_path)
        except Exception:
            for p in chunk_paths:
                if os.path.exists(p):
                    try: os.unlink(p)
                    except: pass
            raise
        transcript = "\n".join(all_text)
        language = detected_language
    else:
        segments, info = model.transcribe(audio_path, language=lang_param, beam_size=1, vad_filter=True)
        transcript = "\n".join(s.text.strip() for s in segments)
        language = info.language

    return {"transcript": transcript, "language": language}

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--oneshot', metavar='AUDIO_PATH', help='단발성 변환 후 JSON 출력하고 종료')
    args = parser.parse_args()

    whisper_model = os.environ.get("WHISPER_MODEL", "medium")
    cpu_threads = int(os.environ.get("WHISPER_CPU_THREADS", min(os.cpu_count() or 4, 8)))
    print(f"READY:loading model={whisper_model} cpu_threads={cpu_threads}", file=sys.stderr, flush=True)
    model = WhisperModel(whisper_model, device="cpu", compute_type="int8", cpu_threads=cpu_threads)
    print("READY:ok", file=sys.stderr, flush=True)

    if args.oneshot:
        try:
            result = transcribe(model, args.oneshot)
            print(json.dumps(result, ensure_ascii=False), flush=True)
        except Exception as e:
            print(json.dumps({"error": str(e)}, ensure_ascii=False), flush=True)
        return

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
            language = req.get("language") or None  # "auto" 또는 None이면 자동 감지, "ko"/"en" 등이면 고정
            result = transcribe(model, audio_path, language=language)
            print(json.dumps(result, ensure_ascii=False), flush=True)
        except Exception as e:
            print(json.dumps({"error": str(e)}, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
