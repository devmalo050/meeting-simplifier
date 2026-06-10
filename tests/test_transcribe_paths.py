import sys
import importlib
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def test_transcript_out_dir_uses_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("MS_DATA_DIR", str(tmp_path))
    import transcribe_server
    importlib.reload(transcribe_server)
    out = transcribe_server.transcript_out_dir()
    assert Path(out) == tmp_path / "state"
    assert Path(out).is_dir()
