import sqlite3
from pathlib import Path

from hooks import harvest_commit

# A real commit body from the project this corpus came from. Keeping a true
# sample means the parser is tested against how commits are actually written,
# not against a shape invented to make the parser pass.
BODY = """高度層管「站得上去嗎」，新的 terrain 層管「站在上面會怎樣」。
表放在 sim_map 而不是 sim_battle，因為 A* 的每格成本也要讀它。

- 泥沼：移動 -40%、不能發動衝鋒（專治矛兵與獵犬）
- 道路：移動 +25%、A* 成本 70

踩到的坑：A* 加了地形成本後 octile 啟發式會高估（道路 70 < 基礎 100），
A* 失去最佳性、算出來的路根本不走道路。啟發式乘上最小地形成本當下界。
另一個：第一版測試把地形蓋在 add_squad 的錨點上，但編隊會位移，
六條測試全假綠——改成蓋在單位真正站的格子上。

平衡回歸（探針，零指令）：斷橋雙島大幅改善（獵弓 75% 2/6→6/6、
90% 0/6→4/6），守橋的計畫終於成立。

1015 項測試綠（新增 7 條地形測試），攻守兩場 autotest 通過。
"""


def test_extracts_pitfall_section():
    sections = harvest_commit.parse_sections(BODY)
    assert "踩到的坑" in sections
    assert "octile" in sections["踩到的坑"]


def test_pitfall_section_stops_at_the_blank_line():
    sections = harvest_commit.parse_sections(BODY)
    assert "斷橋雙島" not in sections["踩到的坑"]
    assert "1015" not in sections["踩到的坑"]


def test_section_keeps_its_continuation_lines():
    sections = harvest_commit.parse_sections(BODY)
    assert "假綠" in sections["踩到的坑"]


def test_heading_with_parenthetical_still_matches():
    """Headings are matched by prefix: '平衡（探針，零指令）：' appeared in real
    history and missed an exact '平衡回歸' match by two characters."""
    sections = harvest_commit.parse_sections(BODY)
    assert "平衡" in sections
    assert "獵弓" in sections["平衡"]


def test_bare_prefix_heading_matches():
    body = "平衡（探針，零指令）：斷橋雙島大幅改善。\n"
    assert "平衡" in harvest_commit.parse_sections(body)


def test_difficulty_regression_is_also_a_heading():
    body = "難度回歸（探針）：三套班底在層 1 都 6/6。\n"
    assert "難度" in harvest_commit.parse_sections(body)


def test_the_full_heading_survives_in_the_section_text():
    """Keying on the prefix groups episodes; the specific wording is not lost
    because the section text keeps its own first line."""
    sections = harvest_commit.parse_sections(BODY)
    assert sections["平衡"].startswith("平衡回歸（探針，零指令）")


def test_english_headings_match():
    body = "Pitfall: the sort lambda returned null on one branch.\n"
    assert "Pitfall" in harvest_commit.parse_sections(body)


def test_body_without_headings_yields_nothing():
    assert harvest_commit.parse_sections("just a normal commit\n\nno sections") == {}


def test_prose_mentioning_a_heading_mid_line_is_not_a_section():
    body = "we documented 踩到的坑 in the guide instead of here\n"
    assert harvest_commit.parse_sections(body) == {}


def test_to_episodes_uses_a_schema_legal_type():
    episodes = harvest_commit.to_episodes("feat: 地形屬性", BODY, commit="084f126")
    assert {e["type"] for e in episodes} == {"lesson"}


def test_to_episodes_keeps_the_section_name_as_context():
    episodes = harvest_commit.to_episodes("feat: 地形屬性", BODY, commit="084f126")
    assert {e["context"] for e in episodes} == {"踩到的坑", "平衡"}


def test_to_episodes_summary_carries_the_subject():
    episodes = harvest_commit.to_episodes("feat: 地形屬性", BODY, commit="084f126")
    assert all("地形屬性" in e["summary"] for e in episodes)


def test_to_episodes_ids_are_deterministic():
    a = harvest_commit.to_episodes("feat: x", BODY, commit="084f126")
    b = harvest_commit.to_episodes("feat: x", BODY, commit="084f126")
    assert [e["id"] for e in a] == [e["id"] for e in b]


def test_to_episodes_ids_differ_per_commit():
    a = harvest_commit.to_episodes("feat: x", BODY, commit="084f126")
    b = harvest_commit.to_episodes("feat: x", BODY, commit="deadbee")
    assert {e["id"] for e in a}.isdisjoint({e["id"] for e in b})


def test_to_episodes_empty_for_plain_commit():
    assert harvest_commit.to_episodes("chore: bump", "nothing structured") == []


def test_write_creates_the_table_on_a_fresh_db(tmp_path: Path):
    db = tmp_path / "game.db"
    episodes = harvest_commit.to_episodes("feat: x", BODY, commit="084f126")
    assert harvest_commit.write_episodes(db, episodes) == 2

    rows = sqlite3.connect(db).execute("SELECT type, context FROM episodes").fetchall()
    assert len(rows) == 2
    assert all(r[0] == "lesson" for r in rows)


def test_write_is_idempotent(tmp_path: Path):
    """The hook may fire twice, and a rebuild replays the whole history."""
    db = tmp_path / "game.db"
    episodes = harvest_commit.to_episodes("feat: x", BODY, commit="084f126")
    harvest_commit.write_episodes(db, episodes)
    assert harvest_commit.write_episodes(db, episodes) == 0

    count = sqlite3.connect(db).execute("SELECT count(*) FROM episodes").fetchone()[0]
    assert count == 2


def test_write_respects_the_type_check_constraint(tmp_path: Path):
    db = tmp_path / "game.db"
    harvest_commit.write_episodes(db, harvest_commit.to_episodes("f", BODY, commit="c"))
    conn = sqlite3.connect(db)
    bad = [("x", "pitfall", "c", "s", "o", "sid", "2026-08-13")]
    try:
        conn.executemany(
            "INSERT INTO episodes VALUES (?,?,?,?,?,?,?)", bad
        )
        raised = False
    except sqlite3.IntegrityError:
        raised = True
    assert raised, "the table must carry kg's CHECK(type IN ...) constraint"


def test_write_to_an_unwritable_path_returns_zero(tmp_path: Path):
    """Harvest failures must never block the user's commit."""
    episodes = harvest_commit.to_episodes("feat: x", BODY, commit="084f126")
    assert harvest_commit.write_episodes(tmp_path / "no" / "such" / "d.db", episodes) == 0
