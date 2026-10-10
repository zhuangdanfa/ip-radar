from datetime import date, timedelta

from ipradar.score import metric_signal, score, weekly_series
from ipradar.store import Row


def daily(ip, start, weekly_levels, source="wikipedia", metric="pageviews"):
    rows = []
    d = start
    for level in weekly_levels:
        for _ in range(7):
            rows.append(Row(d.isoformat(), ip, source, metric, level))
            d += timedelta(days=1)
    return rows


START = date(2026, 6, 1)  # 周一


def test_partial_week_is_dropped_for_sum_metrics():
    rows = daily("a", START, [10, 10]) + [Row((START + timedelta(days=14)).isoformat(), "a", "wikipedia", "pageviews", 1)]
    s = weekly_series(rows)[("a", "wikipedia", "pageviews")]
    assert [v for _, v in s] == [70, 70]


def test_metric_signal_needs_eight_weeks():
    assert metric_signal([1] * 7) is None
    g, a = metric_signal([10] * 4 + [20] * 4)
    assert g > 0.6 and a == 0.0


def test_accelerating_ip_outranks_flat_and_falling():
    flat = daily("flat", START, [100] * 12)
    rising = daily("rising", START, [20] * 8 + [40, 60, 90, 130])
    falling = daily("falling", START, [200] * 8 + [150, 120, 90, 70])
    res = score(flat + rising + falling, ["flat", "rising", "falling", "nodata"])
    order = [r.ip_id for r in res]
    assert order[0] == "rising" and order[-1] == "nodata"
    by = {r.ip_id: r for r in res}
    assert by["rising"].momentum == 100 and by["falling"].momentum == 0
    assert by["rising"].stage == "emerging"  # 增长快但关注度不在前一半
    assert by["falling"].stage == "declining"
    assert by["nodata"].stage == "insufficient"
    assert by["rising"].rising_sources == ["wikipedia"]


def test_breadth_counts_sources_not_metrics():
    rows = daily("x", START, [10] * 8 + [30] * 4) + daily("x", START, [50] * 12, source="trends", metric="interest")
    r = score(rows, ["x"])[0]
    assert r.breadth == 0.5 and r.rising_sources == ["wikipedia"]


def test_as_of_ignores_future_rows():
    rows = daily("a", START, [10] * 8 + [100] * 4)
    early = score(rows, ["a"], as_of=START + timedelta(days=8 * 7 - 1))[0]
    assert early.growth == 0.0
