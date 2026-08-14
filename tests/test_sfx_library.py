"""The library is the audio equivalent of craft.db: a store that outlives any
one game. Searching it before generating is the point, so these tests are
mostly about not silently returning nothing.
"""

import json
from pathlib import Path

import sfx_gen

ITEM = {
    "id": "abc",
    "title": "sword_shield_hit",
    "type": "sfx",
    "durationSec": 1.2,
    "base": "sword striking wooden shield",
    "finalCaption": "sword striking wooden shield, heavy impact thud, fast decay",
    "audioPath": "C:/lib/audio/abc.wav",
}
OTHER = {**ITEM, "id": "def", "title": "boot_on_dirt", "base": "armored boot on dirt",
         "finalCaption": "single armored boot plants on packed dirt, dull thud"}
MUSIC = {**ITEM, "id": "ghi", "title": "tense_loop", "type": "bgm",
         "base": "tense strings", "finalCaption": "tense strings, slow build"}


def _index(tmp_path: Path, data) -> Path:
    path = tmp_path / "library.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_reads_the_wrapped_shape_the_library_actually_uses(tmp_path: Path):
    """The real index is {"items": [...]}. Treating its values as items gave a
    list-of-lists, every entry failed the dict check, and the search returned
    zero for a query that should have matched three."""
    index = _index(tmp_path, {"items": [ITEM, OTHER]})
    assert len(sfx_gen.search_library(index)) == 2


def test_reads_a_bare_list(tmp_path: Path):
    assert len(sfx_gen.search_library(_index(tmp_path, [ITEM]))) == 1


def test_reads_a_dict_of_items(tmp_path: Path):
    assert len(sfx_gen.search_library(_index(tmp_path, {"abc": ITEM}))) == 1


def test_matches_on_caption_not_just_title(tmp_path: Path):
    index = _index(tmp_path, {"items": [ITEM, OTHER]})
    found = sfx_gen.search_library(index, "packed dirt")
    assert [f["id"] for f in found] == ["def"]


def test_matching_is_case_insensitive(tmp_path: Path):
    index = _index(tmp_path, {"items": [ITEM]})
    assert len(sfx_gen.search_library(index, "SWORD")) == 1


def test_an_empty_query_returns_everything(tmp_path: Path):
    index = _index(tmp_path, {"items": [ITEM, OTHER, MUSIC]})
    assert len(sfx_gen.search_library(index)) == 3


def test_kind_filters_music_from_effects(tmp_path: Path):
    index = _index(tmp_path, {"items": [ITEM, MUSIC]})
    assert [f["id"] for f in sfx_gen.search_library(index, kind="bgm")] == ["ghi"]


def test_a_miss_is_empty_not_an_error(tmp_path: Path):
    index = _index(tmp_path, {"items": [ITEM]})
    assert sfx_gen.search_library(index, "harpsichord") == []


def test_results_carry_the_path_so_the_sound_can_be_adopted(tmp_path: Path):
    """Adoption is just `post` on this path -- the library entry is generic,
    and post-processing is what fits it to this game's levels."""
    index = _index(tmp_path, {"items": [ITEM]})
    assert sfx_gen.search_library(index)[0]["path"] == "C:/lib/audio/abc.wav"


def test_find_library_uses_the_env_var(tmp_path: Path, monkeypatch):
    home = tmp_path / "ACE_Studio"
    (home / "library").mkdir(parents=True)
    (home / "library" / "library.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("ACE_STUDIO_HOME", str(home))
    monkeypatch.chdir(tmp_path)
    assert sfx_gen.find_library() == home / "library" / "library.json"


def test_find_library_returns_none_when_absent(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ACE_STUDIO_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert sfx_gen.find_library() is None
