from pathlib import Path

import pytest

import blender_gen


def test_env_override_wins(tmp_path: Path):
    exe = tmp_path / "blender.exe"
    exe.touch()
    assert blender_gen.find_blender({"BLENDER_PATH": str(exe)}) == exe


def test_env_pointing_at_nothing_is_ignored(tmp_path: Path):
    found = blender_gen.find_blender({"BLENDER_PATH": str(tmp_path / "nope.exe")})
    assert found is None or found.exists()


def test_missing_blender_returns_none(monkeypatch):
    monkeypatch.setattr(blender_gen, "CANDIDATE_PATHS", ())
    monkeypatch.setattr(blender_gen.shutil, "which", lambda _: None)
    assert blender_gen.find_blender({}) is None


def test_conventional_path_is_searched(tmp_path: Path, monkeypatch):
    exe = tmp_path / "blender.exe"
    exe.touch()
    monkeypatch.setattr(blender_gen, "CANDIDATE_PATHS", (exe,))
    monkeypatch.setattr(blender_gen.shutil, "which", lambda _: None)
    assert blender_gen.find_blender({}) == exe


def test_verify_outputs_accepts_a_real_file(tmp_path: Path):
    glb = tmp_path / "unit.glb"
    glb.write_bytes(b"glTF" + b"\x00" * 200)
    assert blender_gen.verify_outputs(tmp_path, ".glb") == [glb]


def test_verify_outputs_rejects_an_empty_file(tmp_path: Path):
    """Blender exits 0 after a script error, leaving a zero-byte export."""
    (tmp_path / "unit.glb").touch()
    with pytest.raises(blender_gen.NoOutput):
        blender_gen.verify_outputs(tmp_path, ".glb")


def test_verify_outputs_rejects_nothing_at_all(tmp_path: Path):
    with pytest.raises(blender_gen.NoOutput):
        blender_gen.verify_outputs(tmp_path, ".glb")


def test_build_command_runs_headless(tmp_path: Path):
    exe = tmp_path / "blender.exe"
    script = tmp_path / "make_units.py"
    command = blender_gen.build_command(exe, script)
    assert command == [str(exe), "--background", "--python", str(script)]
