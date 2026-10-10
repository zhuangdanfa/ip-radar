from ipradar.seeds import load_seeds
from ipradar.store import Row, read_rows, upsert_rows


def test_seed_file_loads_and_has_required_fields():
    seeds = load_seeds()
    assert len(seeds) >= 40
    for s in seeds:
        assert s.ip_id and s.name_zh and s.wikipedia_title and s.search_term


def test_upsert_overwrites_same_key(tmp_path):
    f = tmp_path / "m.csv"
    upsert_rows([Row("2026-10-01", "a", "wikipedia", "pageviews", 10)], f)
    upsert_rows([Row("2026-10-01", "a", "wikipedia", "pageviews", 12),
                 Row("2026-10-02", "a", "wikipedia", "pageviews", 5)], f)
    rows = read_rows(f)
    assert [(r.date, r.value) for r in rows] == [("2026-10-01", 12), ("2026-10-02", 5)]


def test_replace_series_drops_old_points(tmp_path):
    f = tmp_path / "m.csv"
    upsert_rows([Row("2026-01-04", "a", "trends", "interest", 50), Row("2026-01-04", "b", "trends", "interest", 7)], f)
    upsert_rows([Row("2026-01-11", "a", "trends", "interest", 80)], f, replace_series=True)
    rows = read_rows(f)
    assert {(r.ip_id, r.date) for r in rows} == {("a", "2026-01-11"), ("b", "2026-01-04")}
