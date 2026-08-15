"""Machine-local configuration, read from .env.

Paths and service endpoints differ per machine, and asset backends differ per
person: procedural models in Blender alongside cloud image generation is a
normal setup, so the choice is one axis per kind rather than a single
local-or-cloud switch.

Real environment variables win over the file, so a one-off override needs no
edit. Nothing here is required -- a missing value means "not available", and
callers degrade rather than fail.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"

# Backend per asset kind, with the default first. `none` means the project
# does not generate that kind at all.
BACKENDS: dict[str, tuple[str, ...]] = {
    "ASSET_3D": ("blender", "tripo3d", "none"),
    "ASSET_2D": ("comfyui", "gemini", "grok", "none"),
    "ASSET_AUDIO": ("ace", "none"),
}

# What each backend needs before it can work. Checked by /setup, not enforced
# here -- publishing with an unusable backend is the user's call to make.
REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "blender": ("BLENDER_PATH",),
    "tripo3d": ("TRIPO3D_API_KEY",),
    "comfyui": ("COMFYUI_URL",),
    "gemini": ("GOOGLE_API_KEY",),
    "grok": ("XAI_API_KEY",),
    "ace": (),  # located by path, see external.py
    "none": (),
}

_LOCAL = {"blender", "comfyui", "ace"}

_LABELS = {
    "blender": "Blender procedural (local, free)",
    "tripo3d": "Tripo3D image-to-3D (cloud, paid)",
    "comfyui": "ComfyUI (local, free)",
    "gemini": "Gemini (cloud, paid)",
    "grok": "Grok (cloud, paid)",
    "ace": "ACE Studio (local, free, reuses its library)",
    "none": "not used",
}


class UnknownBackend(Exception):
    """A backend name outside the allowed set for its kind."""


def parse_env(text: str) -> dict[str, str]:
    """Parse KEY=VALUE lines. No interpolation, no quoting rules -- values are
    paths and URLs, and a config format with surprises in it is a bug source."""
    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def load(env_file: Path | None = None, environ: dict[str, str] | None = None) -> dict[str, str]:
    """Merge .env with the real environment. The environment wins."""
    path = ENV_FILE if env_file is None else Path(env_file)
    values: dict[str, str] = {}
    if path.is_file():
        values.update(parse_env(path.read_text(encoding="utf-8")))

    environ = os.environ if environ is None else environ
    for key in list(BACKENDS) + [k for reqs in REQUIREMENTS.values() for k in reqs] + [
        "GODOGEN_KG_HOME",
        "ACE_STUDIO_HOME",
        "GAMES_ROOT",
        "GODOT_PATH",
    ]:
        if environ.get(key):
            values[key] = environ[key]

    return {k: v for k, v in values.items() if v}


def backend(kind: str, config: dict[str, str] | None = None) -> str:
    """The selected backend for one asset kind, defaulting to the first."""
    if kind not in BACKENDS:
        raise UnknownBackend(f"unknown asset kind: {kind!r}")
    config = load() if config is None else config
    choice = config.get(kind, BACKENDS[kind][0])
    if choice not in BACKENDS[kind]:
        raise UnknownBackend(
            f"{kind}={choice!r} is not one of {', '.join(BACKENDS[kind])}"
        )
    return choice


def missing_requirements(config: dict[str, str] | None = None) -> dict[str, list[str]]:
    """{backend: [settings it needs that are not set]} for the chosen backends."""
    config = load() if config is None else config
    gaps: dict[str, list[str]] = {}
    for kind in BACKENDS:
        chosen = backend(kind, config)
        absent = [key for key in REQUIREMENTS[chosen] if not config.get(key)]
        if absent:
            gaps[chosen] = absent
    return gaps


def describe(config: dict[str, str] | None = None) -> str:
    """One line naming the chosen backends, rendered into the asset skill so
    the agent in a game repo knows which pipeline this project uses."""
    config = load() if config is None else config
    parts = [
        f"3D = {_LABELS[backend('ASSET_3D', config)]}",
        f"2D = {_LABELS[backend('ASSET_2D', config)]}",
        f"audio = {_LABELS[backend('ASSET_AUDIO', config)]}",
    ]
    return " · ".join(parts)


def games_root(config: dict[str, str] | None = None) -> Path:
    """Where new game repos are created.

    A published game is its own repository with its own remote -- the same
    kind of thing as the knowledge engine and the audio studio, and kept
    beside the generator rather than inside it. Nesting one repo in another
    means the inner ones are physically present and invisible to version
    control, and every boundary that blurred today cost something.

    Having a default at all is the point: otherwise each game lands wherever
    was convenient that day, which is how one ended up somewhere it had to be
    hunted down and moved.
    """
    config = load() if config is None else config
    configured = config.get("GAMES_ROOT")
    return Path(configured) if configured else REPO_ROOT.parent / "games"


def uses_cloud(config: dict[str, str] | None = None) -> bool:
    config = load() if config is None else config
    return any(
        backend(kind, config) not in _LOCAL | {"none"} for kind in BACKENDS
    )
