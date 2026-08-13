from pathlib import Path

import pytest

from scripts import bootstrap


@pytest.fixture
def stubbed(monkeypatch):
    """Stub the two subprocesses and the priority write; the assertions here
    are about the verification gate, not about node or sqlite."""
    monkeypatch.setattr(bootstrap, "_run", lambda *a, **k: "")
    monkeypatch.setattr(
        bootstrap.seed_priority, "seed", lambda db, corpus: {"principles > x": 300}
    )


def test_zero_vectors_is_a_failure(tmp_path: Path, monkeypatch, stubbed):
    """The failure this exists to catch: import-skills.js writes no vectors on
    a fresh process and still prints success."""
    monkeypatch.setattr(bootstrap, "count_vectors", lambda *a: (20, 0))

    with pytest.raises(bootstrap.BootstrapFailed, match="silently dead"):
        bootstrap.bootstrap(tmp_path, tmp_path / "craft.db", bootstrap.REPO_ROOT / "knowledge")


def test_partial_vectors_is_also_a_failure(tmp_path: Path, monkeypatch, stubbed):
    monkeypatch.setattr(bootstrap, "count_vectors", lambda *a: (20, 12))

    with pytest.raises(bootstrap.BootstrapFailed):
        bootstrap.bootstrap(tmp_path, tmp_path / "craft.db", bootstrap.REPO_ROOT / "knowledge")


def test_empty_import_is_a_failure(tmp_path: Path, monkeypatch, stubbed):
    monkeypatch.setattr(bootstrap, "count_vectors", lambda *a: (0, 0))

    with pytest.raises(bootstrap.BootstrapFailed):
        bootstrap.bootstrap(tmp_path, tmp_path / "craft.db", bootstrap.REPO_ROOT / "knowledge")


def test_a_full_index_reports_its_principle_count(tmp_path: Path, monkeypatch, stubbed):
    monkeypatch.setattr(bootstrap, "count_vectors", lambda *a: (20, 20))
    monkeypatch.setattr(
        bootstrap.seed_priority, "seed", lambda db, corpus: {"principles > x": 300, "pitfalls > y": 100}
    )

    stats = bootstrap.bootstrap(tmp_path, tmp_path / "craft.db", bootstrap.REPO_ROOT / "knowledge")
    assert stats == {"nodes": 20, "vectors": 20, "principles": 1}


def test_a_corpus_that_matches_nothing_is_a_failure(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(bootstrap, "_run", lambda *a, **k: "")
    monkeypatch.setattr(bootstrap.seed_priority, "seed", lambda db, corpus: {})

    with pytest.raises(bootstrap.BootstrapFailed, match="matched"):
        bootstrap.bootstrap(tmp_path, tmp_path / "craft.db", tmp_path / "empty")
