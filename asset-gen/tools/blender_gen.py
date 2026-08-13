#!/usr/bin/env python3
"""Run a Blender modelling script headless and check that it produced meshes.

This is a driver, not a modeller. The geometry lives in your own `bpy` script;
this finds Blender, runs it with a timeout, and refuses to report success on
an empty export -- Blender exits 0 after a Python error, leaving a zero-byte
file behind.

    python blender_gen.py tools/make_units.py --out assets/models

Why procedural instead of generative 3D: the same script run a hundred times
produces the same models, and changing one parameter changes the shape. A
generative pipeline drifts between batches, so your units end up looking like
they came from four different games. See asset-gen/blender.md for the
modelling conventions -- the orientation and camera traps in particular.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

CANDIDATE_PATHS = (
    Path(r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe"),
    Path(r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"),
    Path("/Applications/Blender.app/Contents/MacOS/Blender"),
    Path("/usr/bin/blender"),
)

DEFAULT_TIMEOUT_S = 600


class NoOutput(Exception):
    """Blender ran but produced nothing usable."""


def find_blender(env: dict[str, str] | None = None) -> Path | None:
    """BLENDER_PATH, then the conventional install locations, then PATH."""
    env = os.environ if env is None else env

    override = env.get("BLENDER_PATH")
    if override and Path(override).is_file():
        return Path(override)

    for candidate in CANDIDATE_PATHS:
        if candidate.is_file():
            return candidate

    found = shutil.which("blender")
    return Path(found) if found else None


def build_command(blender: Path, script: Path) -> list[str]:
    return [str(blender), "--background", "--python", str(script)]


def verify_outputs(out_dir: Path, suffix: str = ".glb") -> list[Path]:
    """Blender exits 0 after a script error, so an exit code proves nothing."""
    files = sorted(p for p in Path(out_dir).glob(f"*{suffix}") if p.is_file())
    non_empty = [p for p in files if p.stat().st_size > 0]
    if not non_empty:
        raise NoOutput(
            f"no non-empty {suffix} files in {out_dir} "
            f"({len(files)} file(s) found) -- check Blender's stderr"
        )
    return non_empty


def run(
    script: Path | str,
    out_dir: Path | str,
    suffix: str = ".glb",
    timeout: int = DEFAULT_TIMEOUT_S,
    env: dict[str, str] | None = None,
) -> dict:
    blender = find_blender(env)
    if blender is None:
        raise NoOutput(
            "blender not found -- set BLENDER_PATH or put blender on PATH"
        )

    script = Path(script)
    if not script.is_file():
        raise NoOutput(f"script not found: {script}")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    before = {p: p.stat().st_mtime for p in out.glob(f"*{suffix}")}

    print(f"blender: {script.name}", file=sys.stderr)
    try:
        result = subprocess.run(
            build_command(blender, script),
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise NoOutput(f"blender timed out after {timeout}s")

    if result.returncode != 0:
        print(result.stderr[-2000:], file=sys.stderr)
        raise NoOutput(f"blender exited {result.returncode}")

    produced = verify_outputs(out, suffix)
    fresh = [p for p in produced if before.get(p) != p.stat().st_mtime]
    return {
        "ok": True,
        "cost_cents": 0,
        "written": [str(p) for p in (fresh or produced)],
        "count": len(fresh or produced),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="blender_gen.py")
    parser.add_argument("script", help="a bpy script that exports models")
    parser.add_argument("--out", required=True, help="where the script writes models")
    parser.add_argument("--suffix", default=".glb")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S)
    args = parser.parse_args(argv)

    try:
        report = run(args.script, args.out, args.suffix, args.timeout)
    except (NoOutput, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1

    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
