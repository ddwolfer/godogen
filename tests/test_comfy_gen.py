import copy

import pytest

import comfy_gen

WORKFLOW = {
    "3": {"class_type": "KSampler", "inputs": {"seed": 1, "steps": 12, "cfg": 1.0}},
    "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "placeholder"}},
    "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "out"}},
}


def test_style_prompt_is_locked_and_non_empty():
    assert len(comfy_gen.STYLE_PROMPT) > 50


def test_build_prompt_puts_the_subject_first():
    prompt = comfy_gen.build_prompt("a crude short sword, pitted blade")
    assert prompt.startswith("a crude short sword, pitted blade")


def test_build_prompt_always_carries_the_style():
    """One locked style string across every image is what stops a 29-icon set
    from looking like 29 separate little worlds."""
    for subject in ("a shield", "a healing potion", "a war banner"):
        assert comfy_gen.STYLE_PROMPT in comfy_gen.build_prompt(subject)


def test_build_prompt_rejects_an_empty_subject():
    with pytest.raises(ValueError):
        comfy_gen.build_prompt("   ")


def test_patch_workflow_sets_prompt_seed_and_size():
    patched = comfy_gen.patch_workflow(WORKFLOW, "a shield", seed=99, width=768, height=768)
    assert patched["6"]["inputs"]["text"] == "a shield"
    assert patched["3"]["inputs"]["seed"] == 99
    assert patched["5"]["inputs"]["width"] == 768
    assert patched["5"]["inputs"]["height"] == 768


def test_patch_workflow_does_not_mutate_the_template():
    before = copy.deepcopy(WORKFLOW)
    comfy_gen.patch_workflow(WORKFLOW, "a shield", seed=99, width=768, height=768)
    assert WORKFLOW == before


def test_patch_workflow_keeps_untouched_inputs():
    patched = comfy_gen.patch_workflow(WORKFLOW, "a shield", seed=99, width=768, height=768)
    assert patched["3"]["inputs"]["steps"] == 12
    assert patched["9"]["inputs"]["filename_prefix"] == "out"


def test_patch_workflow_without_a_text_node_raises():
    with pytest.raises(comfy_gen.WorkflowMismatch):
        comfy_gen.patch_workflow({"1": {"class_type": "SaveImage", "inputs": {}}}, "x", 1, 512, 512)


def test_patch_workflow_patches_only_the_positive_prompt():
    """Two CLIPTextEncode nodes means positive and negative; overwriting the
    negative one silently inverts the image."""
    two = dict(WORKFLOW)
    two["7"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, text"}}
    patched = comfy_gen.patch_workflow(two, "a shield", seed=1, width=512, height=512,
                                       positive_node="6")
    assert patched["6"]["inputs"]["text"] == "a shield"
    assert patched["7"]["inputs"]["text"] == "blurry, text"


def test_ambiguous_text_nodes_require_an_explicit_choice():
    two = dict(WORKFLOW)
    two["7"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, text"}}
    with pytest.raises(comfy_gen.WorkflowMismatch):
        comfy_gen.patch_workflow(two, "a shield", seed=1, width=512, height=512)
