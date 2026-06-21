# scripts/transcribe_server.py
# --oneshot PATH: 오디오를 변환해 JSON({"transcript","language"})을 stdout으로 출력하고 종료
import sys
import json
import os
import wave
import tempfile
from faster_whisper import WhisperModel

from paths import state_dir

CHUNK_SECS = 600
# 겹침 구간을 두면 split 후 단순 연결 시 경계 텍스트가 중복 전사되므로 0으로 둔다
# (긴 녹음에서 청크 경계 단어 손실 가능성 < 중복으로 인한 회의록 오염)
OVERLAP_SECS = 0

def transcript_out_dir():
    return str(state_dir())

def _data_chunk_offset(path):
    # node-record-lpcm16은 data 청크 크기를 부정확하게 기록하므로 크기 필드는 신뢰하지 않는다.
    # data 청크 시작 오프셋만 raw RIFF 파싱으로 구하고(LIST 등 선행 청크 대응), 길이는 파일 크기에서 계산한다.
    with open(path, 'rb') as f:
        if f.read(4) != b'RIFF':
            return None
        f.seek(4, 1)
        if f.read(4) != b'WAVE':
            return None
        while True:
            header = f.read(8)
            if len(header) < 8:
                return None
            chunk_id = header[0:4]
            chunk_size = int.from_bytes(header[4:8], 'little')
            if chunk_id == b'data':
                return f.tell()
            f.seek(chunk_size + (chunk_size & 1), 1)


def read_wav_duration(path):
    try:
        with wave.open(path, 'r') as f:
            params = f.getparams()
        frame_size = params.nchannels * params.sampwidth
        offset = _data_chunk_offset(path)
        if offset is None:
            return 0
        file_size = os.path.getsize(path)
        actual_frames = max(0, file_size - offset) // frame_size
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
    tmp.close()
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
            tmp.close()
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
    parser.add_argument('--oneshot', metavar='AUDIO_PATH', required=True, help='오디오 변환 후 JSON 출력하고 종료')
    args = parser.parse_args()

    whisper_model = os.environ.get("WHISPER_MODEL", "medium")
    cpu_threads = int(os.environ.get("WHISPER_CPU_THREADS", min(os.cpu_count() or 4, 8)))
    print(f"READY:loading model={whisper_model} cpu_threads={cpu_threads}", file=sys.stderr, flush=True)
    model = WhisperModel(whisper_model, device="cpu", compute_type="int8", cpu_threads=cpu_threads)
    print("READY:ok", file=sys.stderr, flush=True)

    try:
        result = transcribe(model, args.oneshot)
        # 트랜스크립트 전문을 파일로 저장한다. 회의록의 "전체 트랜스크립트"는 save_meeting.py가
        # 이 파일을 읽어 코드로 붙이므로, LLM이 긴 트랜스크립트를 다시 타이핑하다 잘리는 일이 없다.
        try:
            out_dir = transcript_out_dir()
            os.makedirs(out_dir, exist_ok=True)
            stem = os.path.splitext(os.path.basename(args.oneshot))[0]
            tfile = os.path.join(out_dir, f"transcript_{stem}.txt")
            with open(tfile, "w", encoding="utf-8") as f:
                f.write(result.get("transcript", ""))
            result["transcript_file"] = tfile
        except Exception:
            pass
        print(json.dumps(result, ensure_ascii=False), flush=True)
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
