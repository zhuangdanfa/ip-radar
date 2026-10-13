import json
from datetime import date

from ipradar.config import Region
from ipradar.site import build_site
from ipradar.store import upsert_rows
from tests.test_score import START, daily


def make_region(tmp_path, rid, rows):
    seed_file = tmp_path / f"{rid}.csv"
    seed_file.write_text("ip_id,name_zh,name_en,type,wikipedia_title,search_term,subreddit\n"
                         "a,甲,A,动画,A,A,\nb,乙,B,游戏,B,B,\n", "utf-8")
    region = Region(rid, rid.upper(), seed_file, tmp_path / rid, tmp_path / "reports" / rid, ("wikipedia",))
    if rows:
        upsert_rows(rows, region.metrics_file)
    return region


def test_build_site_writes_page_and_data(tmp_path):
    rows = daily("a", START, [10] * 4 + [30] * 4) + [r._replace(source="trends", metric="interest") for r in daily("a", START, [5] * 8)]
    na = make_region(tmp_path, "na", rows)
    cn = make_region(tmp_path, "cn", [])
    missing = Region("xx", "XX", tmp_path / "none.csv", tmp_path / "xx", tmp_path / "xx", ())
    out = build_site([na, cn, missing], date(2026, 7, 27), out_dir=tmp_path / "site")
    assert (out / "index.html").read_text("utf-8").startswith("<!doctype html>")
    data = json.loads((out / "data.json").read_text("utf-8"))
    assert data["as_of"] == "2026-07-27" and [r["id"] for r in data["regions"]] == ["na", "cn"]
    a, b = data["regions"][0]["items"]
    assert a["rank"] == 1 and a["name_zh"] == "甲"
    assert [c["source"] for c in a["charts"]] == ["wikipedia", "trends"]  # 固定顺序
    assert a["charts"][0]["points"][-1] == ["2026-07-20", 210.0]
    assert b["rank"] is None and b["charts"] == []
    assert all(it["rank"] is None for it in data["regions"][1]["items"])  # 还没数据的地区也列出来
