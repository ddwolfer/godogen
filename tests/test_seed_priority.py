import sqlite3
from pathlib import Path

from scripts import seed_priority

CORPUS = Path(__file__).resolve().parent.parent / "knowledge"


def test_principles_outrank_patterns_outrank_pitfalls():
    p = seed_priority.priority_of(CORPUS / "principles" / "mechanism-weight.md", CORPUS)
    q = seed_priority.priority_of(CORPUS / "patterns" / "deterministic-tick-sim.md", CORPUS)
    r = seed_priority.priority_of(CORPUS / "pitfalls" / "windows-toolchain.md", CORPUS)
    assert p > q > r


def test_readme_is_excluded():
    assert seed_priority.priority_of(CORPUS / "README.md", CORPUS) == 0


def test_frontmatter_override_wins(tmp_path: Path):
    corpus = tmp_path / "knowledge"
    (corpus / "pitfalls").mkdir(parents=True)
    entry = corpus / "pitfalls" / "urgent.md"
    entry.write_text(
        "---\nsource: x\nverified: true\npriority: 999\n---\n# t\n", encoding="utf-8"
    )
    assert seed_priority.priority_of(entry, corpus) == 999


def test_every_principle_survives_the_post_compact_budget():
    """The whole point: a 10-slot budget that dropped all seven principles is
    how the agent ended up with traps and no method."""
    ranked = sorted(
        ((seed_priority.priority_of(p, CORPUS), p) for p in CORPUS.rglob("*.md")),
        key=lambda kv: -kv[0],
    )
    top = {p.stem for _, p in ranked[:10]}
    principles = {p.stem for p in (CORPUS / "principles").glob("*.md")}
    assert principles <= top, f"dropped: {principles - top}"


def test_node_key_normalises_the_importer_naming():
    """import-skills.js names nodes 'pitfalls > windows-toolchain'."""
    assert seed_priority.node_key("pitfalls > windows-toolchain") == "pitfalls/windows-toolchain"
    assert seed_priority.node_key("pitfalls\\windows-toolchain") == "pitfalls/windows-toolchain"


def test_seed_writes_access_count(tmp_path: Path):
    db = tmp_path / "craft.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE nodes (id TEXT PRIMARY KEY, name TEXT, access_count INTEGER)")
    conn.executemany(
        "INSERT INTO nodes VALUES (?,?,0)",
        [("1", "principles > mechanism-weight"), ("2", "pitfalls > windows-toolchain")],
    )
    conn.commit()
    conn.close()

    applied = seed_priority.seed(db, CORPUS)
    assert len(applied) == 2

    counts = dict(sqlite3.connect(db).execute("SELECT name, access_count FROM nodes"))
    assert counts["principles > mechanism-weight"] > counts["pitfalls > windows-toolchain"]


def test_seed_ignores_nodes_with_no_matching_file(tmp_path: Path):
    db = tmp_path / "craft.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE nodes (id TEXT PRIMARY KEY, name TEXT, access_count INTEGER)")
    conn.execute("INSERT INTO nodes VALUES ('1','something > unrelated',7)")
    conn.commit()
    conn.close()

    assert seed_priority.seed(db, CORPUS) == {}
    left = sqlite3.connect(db).execute("SELECT access_count FROM nodes").fetchone()[0]
    assert left == 7, "unrelated nodes must not be touched"
