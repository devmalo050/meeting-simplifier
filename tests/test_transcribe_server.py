import importlib
import os
import sys
import types
import wave
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _inject_faster_whisper():
    """faster_whisper를 가짜 모듈로 sys.modules에 주입해 import 비용 제거."""
    if "faster_whisper" not in sys.modules:
        fake = types.ModuleType("faster_whisper")
        fake.WhisperModel = object
        sys.modules["faster_whisper"] = fake


_inject_faster_whisper()


def _load_ts():
    if "transcribe_server" in sys.modules:
        importlib.reload(sys.modules["transcribe_server"])
    else:
        import transcribe_server  # noqa: F401
    return sys.modules["transcribe_server"]


@pytest.fixture
def ts():
    return _load_ts()


def _make_wav(path, seconds, rate=16000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))


def _make_wav_with_list_chunk(path, seconds, rate=16000, list_bytes=4000):
    """표준 WAV의 data 청크 앞에 LIST 메타데이터 청크를 끼워, 헤더가 44바이트보다 큰 파일 생성."""
    base = path.parent / "_list_base.wav"
    _make_wav(base, seconds, rate)
    raw = bytearray(base.read_bytes())
    base.unlink()
    assert raw[36:40] == b"data"
    payload = b"x" * (list_bytes + (list_bytes & 1))
    list_chunk = b"LIST" + len(payload).to_bytes(4, "little") + payload
    new = raw[:36] + list_chunk + raw[36:]
    riff_size = int.from_bytes(new[4:8], "little") + len(list_chunk)
    new[4:8] = riff_size.to_bytes(4, "little")
    path.write_bytes(bytes(new))


# ---------------------------------------------------------------------------
# read_wav_duration
# ---------------------------------------------------------------------------

def test_read_wav_duration_normal(ts, tmp_path):
    p = tmp_path / "test.wav"
    _make_wav(p, 2.0)
    dur = ts.read_wav_duration(str(p))
    assert abs(dur - 2.0) < 0.1


def test_read_wav_duration_missing_file(ts, tmp_path):
    result = ts.read_wav_duration(str(tmp_path / "nonexistent.wav"))
    assert result == 0


def test_read_wav_duration_with_list_chunk(ts, tmp_path):
    """LIST 청크로 헤더가 44바이트보다 큰 WAV에서도 정확한 길이를 내야 한다."""
    p = tmp_path / "list.wav"
    _make_wav_with_list_chunk(p, 2.0, list_bytes=4000)
    dur = ts.read_wav_duration(str(p))
    assert abs(dur - 2.0) < 0.1


# ---------------------------------------------------------------------------
# fix_wav_header
# ---------------------------------------------------------------------------

def test_fix_wav_header_normal(ts, tmp_path):
    p = tmp_path / "ok.wav"
    _make_wav(p, 1.0)
    result_path, was_fixed = ts.fix_wav_header(str(p))
    assert result_path == str(p)
    assert was_fixed is False


def test_fix_wav_header_corrupted_nframes(ts, tmp_path):
    """nframes가 실제 데이터와 크게 다른 경우 → was_fixed=True, 새 tmp 파일."""
    p = tmp_path / "bad.wav"
    _make_wav(p, 1.0, rate=16000)

    # nframes를 엉뚱한 값으로 덮어써 헤더를 손상
    # WAV RIFF 헤더에서 nframes 필드: bytes 36-39 (data 청크 subchunksize / (nch*sampwidth))
    data = bytearray(p.read_bytes())
    # nframes는 data 청크 크기 / frame_size로 계산되므로
    # data 청크 크기 필드(bytes 40-43)를 0으로 만들어 큰 불일치 유발
    # 실제 WAV 포맷: [RIFF(4)][size(4)][WAVE(4)][fmt (4)][fmtsize(4)][...16bytes...][data(4)][datasize(4)][pcm...]
    # data subchunk size 위치: 4+4+4+4+4+16+4 = 40 (0-indexed)
    # nframes가 파일 크기 기반으로 다르게 계산되도록 datasize를 4로 설정 (실제는 rate*2 bytes)
    data[40] = 4
    data[41] = 0
    data[42] = 0
    data[43] = 0
    p.write_bytes(bytes(data))

    result_path, was_fixed = ts.fix_wav_header(str(p))
    assert was_fixed is True
    assert result_path != str(p)
    assert os.path.exists(result_path)
    os.unlink(result_path)


def test_fix_wav_header_exception_returns_original(ts, tmp_path):
    """읽을 수 없는 파일 → 예외 발생, 원본 경로·False 반환."""
    p = tmp_path / "garbage.wav"
    p.write_bytes(b"not a wav file")
    result_path, was_fixed = ts.fix_wav_header(str(p))
    assert result_path == str(p)
    assert was_fixed is False


def test_fix_wav_header_list_chunk_not_falsely_fixed(ts, tmp_path):
    """LIST 청크가 있어도 nframes가 정상이면 was_fixed=False여야 한다.

    data 오프셋을 0으로 보던 과거 구현은 LIST 크기만큼 actual_frames를 부풀려
    거짓으로 was_fixed=True를 냈다.
    """
    p = tmp_path / "list_ok.wav"
    _make_wav_with_list_chunk(p, 1.0, list_bytes=4000)
    result_path, was_fixed = ts.fix_wav_header(str(p))
    assert was_fixed is False
    assert result_path == str(p)


# ---------------------------------------------------------------------------
# split_wav
# ---------------------------------------------------------------------------

def test_split_wav_single_chunk(ts, tmp_path, monkeypatch):
    p = tmp_path / "short.wav"
    _make_wav(p, 0.5)
    chunks = ts.split_wav(str(p), chunk_secs=10, overlap_secs=0)
    assert len(chunks) == 1
    assert os.path.exists(chunks[0])
    for c in chunks:
        os.unlink(c)


def test_split_wav_multiple_chunks(ts, tmp_path):
    """3초 WAV를 1초 청크로 분할 → 3청크 (chunk_secs는 인자로 직접 전달)."""
    p = tmp_path / "long.wav"
    _make_wav(p, 3.0)
    chunks = ts.split_wav(str(p), chunk_secs=1, overlap_secs=0)
    assert len(chunks) == 3
    for c in chunks:
        assert os.path.exists(c)
        os.unlink(c)


def test_split_wav_chunks_are_valid_wav(ts, tmp_path):
    """청크 파일이 실제로 열리는 WAV여야 한다."""
    p = tmp_path / "audio.wav"
    _make_wav(p, 2.0)
    chunks = ts.split_wav(str(p), chunk_secs=1, overlap_secs=0)
    for c in chunks:
        with wave.open(c, 'r') as f:
            assert f.getnframes() > 0
        os.unlink(c)


# ---------------------------------------------------------------------------
# _transcribe (fake model 주입)
# ---------------------------------------------------------------------------

class _FakeSegment:
    def __init__(self, text):
        self.text = text


class _FakeInfo:
    def __init__(self, language="ko"):
        self.language = language


class _FakeModel:
    """model.transcribe(path, language=, beam_size=, vad_filter=) → (segments, info)"""
    def __init__(self, segments_texts=None, language="ko"):
        self._texts = segments_texts or ["안녕하세요"]
        self._language = language
        self.calls = []

    def transcribe(self, path, language=None, beam_size=1, vad_filter=True):
        self.calls.append({"path": path, "language": language})
        segs = [_FakeSegment(t) for t in self._texts]
        return segs, _FakeInfo(self._language)


def test_transcribe_single_short_audio(ts, tmp_path, monkeypatch):
    p = tmp_path / "short.wav"
    _make_wav(p, 0.5)
    monkeypatch.setattr(ts, "CHUNK_SECS", 600)

    model = _FakeModel(["hello world"], language="en")
    result = ts._transcribe(model, str(p), language=None)

    assert result["transcript"] == "hello world"
    assert result["language"] == "en"
    assert len(model.calls) == 1
    assert model.calls[0]["language"] is None


def test_transcribe_long_audio_splits_into_chunks(ts, tmp_path, monkeypatch):
    """CHUNK_SECS=1, 3초 WAV → 3청크 각각 전사 후 합산."""
    p = tmp_path / "long.wav"
    _make_wav(p, 3.0)
    monkeypatch.setattr(ts, "CHUNK_SECS", 1)

    model = _FakeModel(["chunk"], language="ko")
    result = ts._transcribe(model, str(p))

    assert result["language"] == "ko"
    assert len(model.calls) == 3
    assert result["transcript"].count("chunk") == 3


def test_transcribe_chunk_exception_cleans_up(ts, tmp_path, monkeypatch):
    """청크 처리 중 예외 → 남은 청크 파일 모두 삭제 후 예외 재발생."""
    p = tmp_path / "long.wav"
    _make_wav(p, 3.0)
    monkeypatch.setattr(ts, "CHUNK_SECS", 1)

    call_count = 0

    class _BurstModel:
        def transcribe(self, path, language=None, beam_size=1, vad_filter=True):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("두 번째 청크에서 폭발")
            return [_FakeSegment("ok")], _FakeInfo("ko")

    tracked_chunks = []
    original_split = ts.split_wav

    def _tracking_split(path, chunk_secs, overlap_secs):
        chunks = original_split(path, chunk_secs, overlap_secs)
        tracked_chunks.extend(chunks)
        return chunks

    monkeypatch.setattr(ts, "split_wav", _tracking_split)

    with pytest.raises(RuntimeError, match="두 번째"):
        ts._transcribe(_BurstModel(), str(p))

    # 예외 후 청크 파일들이 모두 정리됐는지 확인
    for c in tracked_chunks:
        assert not os.path.exists(c), f"청크 파일이 남아있음: {c}"


def test_transcribe_language_none_passes_none_to_model(ts, tmp_path, monkeypatch):
    p = tmp_path / "a.wav"
    _make_wav(p, 0.5)
    monkeypatch.setattr(ts, "CHUNK_SECS", 600)

    model = _FakeModel()
    ts._transcribe(model, str(p), language=None)
    assert model.calls[0]["language"] is None


def test_transcribe_language_auto_passes_none_to_model(ts, tmp_path, monkeypatch):
    p = tmp_path / "a.wav"
    _make_wav(p, 0.5)
    monkeypatch.setattr(ts, "CHUNK_SECS", 600)

    model = _FakeModel()
    ts._transcribe(model, str(p), language="auto")
    assert model.calls[0]["language"] is None


def test_transcribe_language_fixed_passes_through(ts, tmp_path, monkeypatch):
    p = tmp_path / "a.wav"
    _make_wav(p, 0.5)
    monkeypatch.setattr(ts, "CHUNK_SECS", 600)

    model = _FakeModel(language="en")
    ts._transcribe(model, str(p), language="en")
    assert model.calls[0]["language"] == "en"
