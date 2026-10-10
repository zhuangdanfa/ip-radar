import json
from datetime import date

from ipradar.score import score
from ipradar.seeds import Seed
from ipradar.site import build_site
from tests.test_score import START, daily

SEEDS = [Seed("a", "甲", "A", "动画", "A", "A", ""), Seed("b", "乙", "B", "游戏", "B", "B", "")]


def test_build_site_writes_page_and_data(tmp_path):
    rows = daily("a", START, [10] * 4 + [30] * 4) + [r._replace(source="trends", metric="interest") for r in daily("a", START, [5] * 8)]
    as_of = date(2026, 7, 27)
    out = build_site(score(rows, ["a", "b"], as_of), SEEDS, rows, as_of, out_dir=tmp_path)
    assert (out / "index.html").read_text("utf-8").startswith("<!doctype html>")
    data = json.loads((out / "data.json").read_text("utf-8"))
    a, b = data["items"]
    assert data["as_of"] == "2026-07-27" and a["rank"] == 1 and a["name_zh"] == "甲"
    assert [c["source"] for c in a["charts"]] == ["wikipedia", "trends"]  # 固定顺序
    assert a["charts"][0]["points"][-1] == ["2026-07-20", 210.0]
    assert b["rank"] is None and b["charts"] == []
