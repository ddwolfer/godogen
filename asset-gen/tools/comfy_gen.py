#!/usr/bin/env python3
"""Local image generation through a running ComfyUI instance.

The approach is deliberately dumb: export a workflow from the ComfyUI UI in
API format, keep it as a template, and patch three fields per image. No
attempt to build graphs programmatically -- the template is whatever you
already got working in the UI.

    python comfy_gen.py --subject "a crude short sword, pitted blade" \\
        -o assets/icons/sword.png --workflow workflows/flux_api.json

The one thing that matters more than the model: every image shares one locked
style string, and only the subject clause changes. That is the difference
between an icon set and a pile of unrelated pictures.

Scope discipline: generate icons and one key visual. Do not generate character
art -- it drifts across batches, is unreadable at board scale, and commits you
to a look before the design has settled.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_HOST = "http://127.0.0.1:8188"

# Locked. Change it and every existing asset stops matching -- if you do change
# it, regenerate the whole set.
STYLE_PROMPT = (
    "game UI icon, single centred object, hand painted, matte finish, "
    "muted desaturated palette of teal-grey rust and bone, one soft magenta "
    "rim light from the upper left, flat dark charcoal background, "
    "no text, no letters, no border, no frame, clean silhouette, "
    "readable at small size"
)

TEXT_NODE = "CLIPTextEncode"
SEED_NODES = ("KSampler", "KSamplerAdvanced", "RandomNoise", "SamplerCustomAdvanced")
SIZE_NODES = ("EmptyLatentImage", "EmptySD3LatentImage", "EmptyLatentImageFlux")


class WorkflowMismatch(Exception):
    """The template does not have the shape the patcher expects."""


def build_prompt(subject: str, style: str = STYLE_PROMPT) -> str:
    """Subject first, then the shared style. Prompt only for what changes."""
    subject = subject.strip()
    if not subject:
        raise ValueError("subject must not be empty")
    return f"{subject}, {style}"


def _nodes_of(workflow: dict, class_types) -> list[str]:
    if isinstance(class_types, str):
        class_types = (class_types,)
    return [
        key for key, node in workflow.items() if node.get("class_type") in class_types
    ]


def patch_workflow(
    workflow: dict,
    prompt: str,
    seed: int,
    width: int,
    height: int,
    positive_node: str | None = None,
) -> dict:
    """Return a copy of the template with prompt, seed and size applied."""
    patched = copy.deepcopy(workflow)

    text_nodes = _nodes_of(patched, TEXT_NODE)
    if not text_nodes:
        raise WorkflowMismatch(f"no {TEXT_NODE} node in the workflow")
    if positive_node is None:
        if len(text_nodes) > 1:
            raise WorkflowMismatch(
                f"{len(text_nodes)} {TEXT_NODE} nodes ({', '.join(sorted(text_nodes))}) -- "
                "pass --positive-node so the negative prompt is not overwritten"
            )
        positive_node = text_nodes[0]
    if positive_node not in patched:
        raise WorkflowMismatch(f"node {positive_node!r} is not in the workflow")
    patched[positive_node]["inputs"]["text"] = prompt

    for key in _nodes_of(patched, SEED_NODES):
        for field in ("seed", "noise_seed"):
            if field in patched[key]["inputs"]:
                patched[key]["inputs"][field] = seed

    for key in _nodes_of(patched, SIZE_NODES):
        patched[key]["inputs"]["width"] = width
        patched[key]["inputs"]["height"] = height

    return patched


def _post(host: str, path: str, payload: dict, timeout: int) -> dict:
    request = urllib.request.Request(
        f"{host}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _get(host: str, path: str, timeout: int) -> bytes:
    with urllib.request.urlopen(f"{host}{path}", timeout=timeout) as response:
        return response.read()


def submit(host: str, workflow: dict, timeout: int = 30) -> str:
    result = _post(host, "/prompt", {"prompt": workflow}, timeout)
    prompt_id = result.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI returned no prompt_id: {result}")
    return prompt_id


def await_image(host: str, prompt_id: str, poll_s: float = 1.0, timeout_s: int = 600) -> bytes:
    """Poll history until the render lands, then fetch the first image."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        history = json.loads(_get(host, f"/history/{prompt_id}", 30).decode("utf-8"))
        entry = history.get(prompt_id)
        if entry:
            for output in entry.get("outputs", {}).values():
                for image in output.get("images", []):
                    query = urllib.parse.urlencode(
                        {
                            "filename": image["filename"],
                            "subfolder": image.get("subfolder", ""),
                            "type": image.get("type", "output"),
                        }
                    )
                    return _get(host, f"/view?{query}", 60)
            raise RuntimeError(f"render finished with no image: {entry.get('status')}")
        time.sleep(poll_s)
    raise TimeoutError(f"no result after {timeout_s}s")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="comfy_gen.py")
    parser.add_argument("--subject", required=True, help="only what changes per image")
    parser.add_argument("-o", "--out", required=True)
    parser.add_argument("--workflow", required=True, help="API-format workflow json")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--positive-node", default=None)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--style", default=STYLE_PROMPT)
    args = parser.parse_args(argv)

    try:
        template = json.loads(Path(args.workflow).read_text(encoding="utf-8"))
        workflow = patch_workflow(
            template,
            build_prompt(args.subject, args.style),
            args.seed,
            args.width,
            args.height,
            args.positive_node,
        )
        print(f"submitting: {args.subject[:60]}...", file=sys.stderr)
        data = await_image(args.host, submit(args.host, workflow))
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    except (
        urllib.error.URLError, OSError, ValueError, RuntimeError,
        TimeoutError, WorkflowMismatch, json.JSONDecodeError,
    ) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1

    print(json.dumps({"ok": True, "path": str(out), "cost_cents": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
