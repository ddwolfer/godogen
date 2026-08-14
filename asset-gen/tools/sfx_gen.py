#!/usr/bin/env python3
"""Local sound-effect generation and post-processing.

Generation is one HTTP call. Post-processing is the part that decides whether
the result is usable: raw output arrives with a tenth of a second of silence
in front, an audible cut at the end, and a level nowhere near the rest of the
library. None of that is optional to fix.

Standard library only -- wave and struct. Nothing to install.

    python sfx_gen.py generate --prompt "..." -o assets/sfx/step.wav
    python sfx_gen.py post raw.wav -o assets/sfx/step.wav --target-dbfs -17

Prompts describe a sound event, not music: event + material + decay + mic
character. "single armored boot plants on packed dirt, soft dull thud with
faint chainmail jingle, dry close mic, very fast decay, no reverb".
"""

from __future__ import annotations

import argparse
import json
import math
import os
import struct
import sys
import urllib.error
import urllib.request
import wave
from pathlib import Path

FULL_SCALE = 32767
DEFAULT_ENDPOINT = "http://127.0.0.1:8002/generate"

# Reference levels measured off an existing library. New sounds land in the
# same band or they are either inaudible or startling.
DEFAULT_TARGET_DBFS = -17.0

ONSET_PEAK_RATIO = 0.02
ONSET_LEAD_MS = 3.0
FADE_MS = 50.0
SHORT_SECONDS = 0.30


# --- pure post-processing -------------------------------------------------


def rms_dbfs(samples: list[int]) -> float:
    """Level of a signal relative to full scale."""
    if not samples:
        return -math.inf
    mean_square = sum(s * s for s in samples) / len(samples)
    if mean_square <= 0:
        return -math.inf
    return 20.0 * math.log10(math.sqrt(mean_square) / FULL_SCALE)


def trim_onset(
    samples: list[int],
    peak_ratio: float = ONSET_PEAK_RATIO,
    lead_ms: float = ONSET_LEAD_MS,
    rate: int = 44100,
) -> list[int]:
    """Drop leading silence, keeping a few ms of lead-in.

    Generated clips routinely open with ~0.1s of nothing, which reads as input
    lag when the sound is tied to a click.
    """
    if not samples:
        return samples
    peak = max(abs(s) for s in samples)
    if peak == 0:
        return samples
    threshold = peak * peak_ratio
    onset = next((i for i, s in enumerate(samples) if abs(s) > threshold), 0)
    lead = int(lead_ms / 1000.0 * rate)
    return samples[max(0, onset - lead) :]


def truncate(samples: list[int], seconds: float, rate: int = 44100) -> list[int]:
    return samples[: int(seconds * rate)]


def fade_out(samples: list[int], ms: float = FADE_MS, rate: int = 44100) -> list[int]:
    """Without this the clip ends on a step, which is audible as a click."""
    n = min(int(ms / 1000.0 * rate), len(samples))
    if n <= 0:
        return list(samples)
    out = list(samples)
    for i in range(n):
        idx = len(out) - n + i
        out[idx] = int(out[idx] * (1.0 - (i + 1) / n))
    return out


def _clamp(value: float) -> int:
    return max(-32768, min(32767, int(round(value))))


def normalize_to(samples: list[int], target_dbfs: float) -> list[int]:
    current = rms_dbfs(samples)
    if current == -math.inf:
        return list(samples)
    gain = 10.0 ** ((target_dbfs - current) / 20.0)
    return [_clamp(s * gain) for s in samples]


def soft_compress(samples: list[int], amount: float = 3.2) -> list[int]:
    """tanh curve: lifts quiet detail while folding peaks in on themselves.

    For a light friction sound -- high peak, tiny body -- plain gain blows the
    peak long before the body becomes audible. This is what gets such a clip
    from -28 dBFS to the rest of the library without clipping.
    """
    denominator = math.tanh(amount)
    out = []
    for s in samples:
        x = s / FULL_SCALE
        out.append(_clamp(math.tanh(x * amount) / denominator * FULL_SCALE))
    return out


# --- wav i/o --------------------------------------------------------------


def read_wav(path: Path | str) -> tuple[list[int], int]:
    """Read a mono 16-bit wav. Stereo is downmixed to the left channel."""
    with wave.open(str(path), "rb") as w:
        channels, width, rate, frames = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(frames)
    if width != 2:
        raise ValueError(f"expected 16-bit samples, got {width * 8}-bit")
    values = list(struct.unpack(f"<{len(raw) // 2}h", raw))
    return (values[::channels] if channels > 1 else values), rate


def write_wav(path: Path | str, samples: list[int], rate: int = 44100) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack(f"<{len(samples)}h", *samples))


# --- pipeline -------------------------------------------------------------


def process(
    src: Path | str,
    dest: Path | str,
    target_dbfs: float = DEFAULT_TARGET_DBFS,
    seconds: float | None = SHORT_SECONDS,
    compress: bool | None = None,
) -> dict:
    """Onset trim, truncate, fade, level. Returns a report."""
    samples, rate = read_wav(src)
    dbfs_in = rms_dbfs(samples)

    samples = trim_onset(samples, rate=rate)
    if seconds:
        samples = truncate(samples, seconds, rate)
    samples = fade_out(samples, rate=rate)

    # A very quiet body cannot be reached by gain alone without blowing the peak.
    if compress is None:
        compress = rms_dbfs(samples) < target_dbfs - 8.0
    if compress:
        samples = soft_compress(samples)
    samples = normalize_to(samples, target_dbfs)

    write_wav(dest, samples, rate)
    return {
        "ok": True,
        "path": str(dest),
        "cost_cents": 0,
        "dbfs_in": round(dbfs_in, 1),
        "dbfs_out": round(rms_dbfs(samples), 1),
        "compressed": compress,
        "seconds": round(len(samples) / rate, 3),
    }


def find_library(home: str | None = None) -> Path | None:
    """Locate ACE Studio's library index.

    The library carries across projects: sounds made for one game are usually
    right for the next. Searching it before generating is the whole point --
    generation is free in money but not in time, and a library entry is one
    you have already listened to.
    """
    roots = [Path(home)] if home else []
    if not home:
        env = os.environ.get("ACE_STUDIO_HOME")
        if env:
            roots.append(Path(env))
        here = Path.cwd()
        roots += [here / "ACE_Studio", here.parent / "ACE_Studio",
                  Path.home() / ".godogen" / "ACE_Studio"]
    for root in roots:
        index = root / "library" / "library.json"
        if index.is_file():
            return index
    return None


def _items_of(data) -> list[dict]:
    """Pull the item list out of a library index.

    The index is `{"items": [...]}` today. Accepting a bare list and a
    dict-of-items too costs three lines and means a format change downgrades
    to fewer results instead of silently zero -- which is exactly how the
    first version of this failed.
    """
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for value in data.values():
        if isinstance(value, list) and any(isinstance(v, dict) for v in value):
            return value
    return [v for v in data.values() if isinstance(v, dict)]


def search_library(index: Path | str, query: str = "", kind: str = "") -> list[dict]:
    """Match a query against captions and titles. Substring, not semantic --
    the agent reading the result can judge relevance better than a score can."""
    items = _items_of(json.loads(Path(index).read_text(encoding="utf-8")))

    needle = query.lower().strip()
    found = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if kind and item.get("type") != kind:
            continue
        haystack = " ".join(
            str(item.get(field, ""))
            for field in ("title", "base", "finalCaption", "extra")
        ).lower()
        if needle and needle not in haystack:
            continue
        found.append(
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "type": item.get("type"),
                "seconds": item.get("durationSec"),
                "caption": item.get("finalCaption") or item.get("base"),
                "path": item.get("audioPath"),
            }
        )
    return found


def generate(prompt: str, dest: Path | str, duration: float, seed: int, steps: int,
             endpoint: str = DEFAULT_ENDPOINT, timeout: int = 300) -> Path:
    """POST to the local SFX engine and save the raw result."""
    body = json.dumps(
        {"prompt": prompt, "duration": duration, "seed": seed, "steps": steps}
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint, data=body, headers={"Content-Type": "application/json"}
    )
    print(f"generating: {prompt[:70]}...", file=sys.stderr)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    raw = payload.get("raw_path")
    if not raw:
        raise RuntimeError(f"engine returned no raw_path: {payload}")
    return Path(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sfx_gen.py")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="generate then post-process")
    gen.add_argument("--prompt", required=True)
    gen.add_argument("-o", "--out", required=True)
    gen.add_argument("--duration", type=float, default=0.8)
    gen.add_argument("--seed", type=int, default=4411)
    gen.add_argument("--steps", type=int, default=80)
    gen.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    gen.add_argument("--target-dbfs", type=float, default=DEFAULT_TARGET_DBFS)
    gen.add_argument("--seconds", type=float, default=SHORT_SECONDS)
    gen.add_argument("--raw", action="store_true", help="skip post-processing")

    lib = sub.add_parser("library", help="search the ACE Studio library first")
    lib.add_argument("--query", default="", help="substring of title or caption")
    lib.add_argument("--kind", default="", choices=["", "sfx", "bgm"])
    lib.add_argument("--home", default=None, help="ACE Studio checkout")

    post = sub.add_parser("post", help="post-process an existing wav")
    post.add_argument("src")
    post.add_argument("-o", "--out", required=True)
    post.add_argument("--target-dbfs", type=float, default=DEFAULT_TARGET_DBFS)
    post.add_argument("--seconds", type=float, default=SHORT_SECONDS)

    args = parser.parse_args(argv)

    try:
        if args.command == "library":
            index = find_library(args.home)
            if index is None:
                raise RuntimeError(
                    "ACE Studio library not found -- set ACE_STUDIO_HOME"
                )
            found = search_library(index, args.query, args.kind)
            print(json.dumps({"ok": True, "count": len(found), "items": found},
                             ensure_ascii=False, indent=2))
            return 0
        if args.command == "generate":
            raw = generate(
                args.prompt, args.out, args.duration, args.seed, args.steps, args.endpoint
            )
            if args.raw:
                report = {"ok": True, "path": str(raw), "cost_cents": 0}
            else:
                report = process(raw, args.out, args.target_dbfs, args.seconds)
        else:
            report = process(args.src, args.out, args.target_dbfs, args.seconds)
    except (urllib.error.URLError, OSError, ValueError, RuntimeError, wave.Error) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stdout)
        return 1

    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
