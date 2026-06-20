import sys
import importlib
import json
import os
import subprocess
from pathlib import Path
import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

PYTHON = str(Path(__file__).resolve().parent.parent / ".venv" / "bin" / "python")


@pytest.fixture
def save_mod(tmp_path, monkeypatch):
    monkeypatch.setenv("MS_DATA_DIR", str(tmp_path))
    import config
    import save_meeting
    importlib.reload(config)
    importlib.reload(save_meeting)
    return save_meeting


# ── resolve_output_dir (기존) ────────────────────────────────────────────────

def test_explicit_arg_wins(save_mod, tmp_path):
    import config
    config.set_output_dir(str(tmp_path / "cfg"))
    assert save_mod.resolve_output_dir("/explicit") == "/explicit"


def test_config_used_when_no_arg(save_mod, tmp_path):
    import config
    config.set_output_dir(str(tmp_path / "cfg"))
    assert save_mod.resolve_output_dir(None) == str(tmp_path / "cfg")


def test_default_when_nothing(save_mod):
    import config
    assert save_mod.resolve_output_dir(None) == config.default_output_dir()


def test_empty_string_falls_through_to_config(save_mod, tmp_path):
    import config
    config.set_output_dir(str(tmp_path / "cfg"))
    assert save_mod.resolve_output_dir("") == str(tmp_path / "cfg")


# ── Step 1: 공백 제목 방어 (RED→GREEN) ──────────────────────────────────────

def test_blank_title_exits_nonzero(tmp_path):
    """main()에 공백만 있는 title 전달 시 비0 종료 + error JSON."""
    minutes_file = tmp_path / "m.txt"
    minutes_file.write_text("내용", encoding="utf-8")

    env = os.environ.copy()
    env["MS_DATA_DIR"] = str(tmp_path)

    result = subprocess.run(
        [
            PYTHON,
            str(SCRIPTS / "save_meeting.py"),
            "--title", "   ",
            "--minutes-file", str(minutes_file),
            "--output-dir", str(tmp_path),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode != 0, "공백 제목은 비0으로 종료해야 함"
    out = json.loads(result.stdout)
    assert "error" in out


def test_empty_title_exits_nonzero(tmp_path):
    """main()에 빈 문자열 title 전달 시 비0 종료."""
    minutes_file = tmp_path / "m.txt"
    minutes_file.write_text("내용", encoding="utf-8")

    env = os.environ.copy()
    env["MS_DATA_DIR"] = str(tmp_path)

    result = subprocess.run(
        [
            PYTHON,
            str(SCRIPTS / "save_meeting.py"),
            "--title", "",
            "--minutes-file", str(minutes_file),
            "--output-dir", str(tmp_path),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode != 0
    out = json.loads(result.stdout)
    assert "error" in out


# ── Step 2: sanitize_dir_name 단위 테스트 ───────────────────────────────────

def test_sanitize_special_chars_removed(save_mod):
    result = save_mod.sanitize_dir_name('file<>:"/\\|?*name')
    assert '<' not in result
    assert '>' not in result
    assert ':' not in result
    assert '"' not in result
    assert '/' not in result
    assert '\\' not in result
    assert '|' not in result
    assert '?' not in result
    assert '*' not in result
    assert 'filename' in result


def test_sanitize_spaces_become_hyphens(save_mod):
    assert save_mod.sanitize_dir_name("hello world test") == "hello-world-test"


def test_sanitize_80_char_truncation(save_mod):
    long_title = "a" * 100
    result = save_mod.sanitize_dir_name(long_title)
    assert len(result) == 80


def test_sanitize_multiple_spaces_single_hyphen(save_mod):
    result = save_mod.sanitize_dir_name("foo   bar")
    assert result == "foo-bar"


# ── Step 3: save_meeting() 직접 호출 테스트 ─────────────────────────────────

def test_save_meeting_md_creates_file(save_mod, tmp_path):
    result = save_mod.save_meeting(
        title="테스트회의",
        minutes="# 회의록\n내용입니다.",
        audio_path="",
        fmt="md",
        output_dir=str(tmp_path),
    )
    saved_dir = Path(result["saved_dir"])
    assert saved_dir.exists()
    md_files = list(saved_dir.glob("*.md"))
    assert len(md_files) == 1
    content = md_files[0].read_text(encoding="utf-8")
    assert "# 회의록" in content
    assert "내용입니다." in content


def test_save_meeting_md_filename_uses_safe_title(save_mod, tmp_path):
    result = save_mod.save_meeting(
        title="My Meeting",
        minutes="본문",
        audio_path="",
        fmt="md",
        output_dir=str(tmp_path),
    )
    saved_dir = Path(result["saved_dir"])
    md_files = list(saved_dir.glob("*.md"))
    assert md_files[0].name == "My-Meeting.md"


def test_save_meeting_txt_creates_file(save_mod, tmp_path):
    result = save_mod.save_meeting(
        title="텍스트회의",
        minutes="텍스트 내용",
        audio_path="",
        fmt="txt",
        output_dir=str(tmp_path),
    )
    saved_dir = Path(result["saved_dir"])
    txt_files = list(saved_dir.glob("*.txt"))
    assert len(txt_files) == 1
    assert "텍스트 내용" in txt_files[0].read_text(encoding="utf-8")


def test_save_meeting_with_transcript(save_mod, tmp_path):
    transcript_file = tmp_path / "transcript.txt"
    transcript_file.write_text("스피커A: 안녕하세요", encoding="utf-8")

    result = save_mod.save_meeting(
        title="트랜스크립트회의",
        minutes="# 요약\n요약입니다.",
        audio_path="",
        fmt="md",
        output_dir=str(tmp_path),
        transcript_file=str(transcript_file),
    )
    saved_dir = Path(result["saved_dir"])
    md_files = list(saved_dir.glob("*.md"))
    content = md_files[0].read_text(encoding="utf-8")
    assert "## 전체 트랜스크립트" in content
    assert "스피커A: 안녕하세요" in content


def test_save_meeting_without_transcript_no_section(save_mod, tmp_path):
    result = save_mod.save_meeting(
        title="노트랜스크립트",
        minutes="# 요약",
        audio_path="",
        fmt="md",
        output_dir=str(tmp_path),
    )
    saved_dir = Path(result["saved_dir"])
    md_files = list(saved_dir.glob("*.md"))
    content = md_files[0].read_text(encoding="utf-8")
    assert "전체 트랜스크립트" not in content


def test_save_meeting_audio_move_success(save_mod, tmp_path):
    audio = tmp_path / "recording.wav"
    audio.write_bytes(b"RIFF")
    out_dir = tmp_path / "output"
    out_dir.mkdir()

    result = save_mod.save_meeting(
        title="오디오회의",
        minutes="내용",
        audio_path=str(audio),
        fmt="md",
        output_dir=str(out_dir),
    )
    assert result.get("audio_moved") is True
    assert "audio_error" not in result


def test_save_meeting_audio_move_failure(save_mod, tmp_path, monkeypatch):
    audio = tmp_path / "recording.wav"
    audio.write_bytes(b"RIFF")
    out_dir = tmp_path / "output"
    out_dir.mkdir()

    def fake_move(src, dst):
        raise OSError("디스크 꽉 참")

    monkeypatch.setattr(save_mod.shutil, "move", fake_move)

    result = save_mod.save_meeting(
        title="실패오디오",
        minutes="내용",
        audio_path=str(audio),
        fmt="md",
        output_dir=str(out_dir),
    )
    assert result.get("audio_moved") is False
    assert "audio_error" in result
    assert "디스크 꽉 참" in result["audio_error"]


def test_save_meeting_permission_error_fallback(save_mod, tmp_path, monkeypatch):
    call_count = {"n": 0}
    real_makedirs = save_mod.os.makedirs

    def fake_makedirs(path, mode=0o777, exist_ok=False):
        if call_count["n"] == 0:
            call_count["n"] += 1
            raise PermissionError("권한 없음")
        real_makedirs(path, mode=mode, exist_ok=exist_ok)

    monkeypatch.setattr(save_mod.os, "makedirs", fake_makedirs)

    result = save_mod.save_meeting(
        title="권한없는회의",
        minutes="내용",
        audio_path="",
        fmt="md",
        output_dir="/no/permission/path",
    )
    assert result["saved_dir"].startswith(str(Path.home() / "Desktop"))


# ── Step 4: docx 경로 테스트 ─────────────────────────────────────────────────

def test_save_docx_import_error_raises_runtime(save_mod, tmp_path, monkeypatch):
    """python-docx를 import 불가 상태로 만들면 RuntimeError 발생."""
    monkeypatch.setitem(sys.modules, "docx", None)
    importlib.reload(save_mod)

    with pytest.raises(RuntimeError, match="python-docx"):
        save_mod.save_docx(str(tmp_path / "test.docx"), "제목", "내용")


def test_save_meeting_docx_import_error(save_mod, tmp_path, monkeypatch):
    """fmt='docx'이고 python-docx 없으면 RuntimeError가 전파됨."""
    monkeypatch.setitem(sys.modules, "docx", None)
    importlib.reload(save_mod)

    with pytest.raises(RuntimeError, match="python-docx"):
        save_mod.save_meeting(
            title="docx없음",
            minutes="내용",
            audio_path="",
            fmt="docx",
            output_dir=str(tmp_path),
        )


def test_save_meeting_docx_real(save_mod, tmp_path):
    """python-docx가 설치돼 있으면 실제 .docx 파일이 생성된다."""
    pytest.importorskip("docx")

    result = save_mod.save_meeting(
        title="실제docx회의",
        minutes="# 제목\n## 소제목\n### 세부목차\n본문 내용입니다.",
        audio_path="",
        fmt="docx",
        output_dir=str(tmp_path),
    )
    saved_dir = Path(result["saved_dir"])
    docx_files = list(saved_dir.glob("*.docx"))
    assert len(docx_files) == 1
    assert docx_files[0].stat().st_size > 0
