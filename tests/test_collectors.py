from datetime import date, datetime, timedelta, timezone

import pandas as pd

from conftest import FakeSession
from ipradar.collectors import reddit, trends, wikipedia, youtube
from ipradar.seeds import Seed

SEED = Seed("bluey", "布鲁伊", "Bluey", "动画", "Bluey_(TV_series)", "Bluey", "bluey")
GONE = Seed("gone", "不存在", "Gone", "动画", "No_Such_Page_xyz", "Gone", "")


def test_wikipedia_follows_redirects_and_skips_missing(tmp_path):
    query = {"query": {
        "redirects": [{"from": "Bluey (TV series)", "to": "Bluey (2018 TV series)"}],
        "pages": [{"title": "Bluey (2018 TV series)"}, {"title": "No Such Page xyz", "missing": True}],
    }}
    s = FakeSession([("w/api.php", 200, query)])
    cache = tmp_path / "titles.json"
    titles = wikipedia.resolve_titles(s, [SEED.wikipedia_title, GONE.wikipedia_title], cache)
    assert titles == {"Bluey_(TV_series)": "Bluey_(2018_TV_series)", "No_Such_Page_xyz": None}
    assert cache.exists()
    s.calls.clear()
    assert wikipedia.resolve_titles(s, [SEED.wikipedia_title], cache) == {"Bluey_(TV_series)": "Bluey_(2018_TV_series)"}
    assert s.calls == []  # 第二次直接读缓存


def test_wikipedia_collect_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(wikipedia, "resolve_titles", lambda session, titles: {SEED.wikipedia_title: "Bluey_(2018_TV_series)", GONE.wikipedia_title: None})
    views = {"items": [{"timestamp": "2026100100", "views": 120}, {"timestamp": "2026100200", "views": 130}]}
    s = FakeSession([("pageviews/per-article", 200, views)])
    rows = wikipedia.collect(s, [SEED, GONE], days=2, today=date(2026, 10, 3))
    assert [(r.date, r.ip_id, r.value) for r in rows] == [("2026-10-01", "bluey", 120), ("2026-10-02", "bluey", 130)]
    assert "/20261001/20261002" in s.calls[0][0]


def test_youtube_rows_and_quota_stop():
    search = {"pageInfo": {"totalResults": 340}, "items": [{"id": {"videoId": "a"}}, {"id": {"videoId": "b"}}]}
    stats = {"items": [{"statistics": {"viewCount": "1000"}}, {"statistics": {"viewCount": "500"}}]}
    s = FakeSession([("/search", 200, search), ("/videos", 200, stats)])
    now = datetime(2026, 10, 10, tzinfo=timezone.utc)
    rows = youtube.collect(s, [SEED], "KEY", now=now)
    assert {(r.metric, r.value) for r in rows} == {("new_videos_7d", 340), ("views_7d", 1500)}
    assert s.calls[0][1]["publishedAfter"] == "2026-10-03T00:00:00Z"
    s403 = FakeSession([("/search", 403, {})])
    assert youtube.collect(s403, [SEED, SEED], "KEY", now=now) == []
    assert len(s403.calls) == 1


def test_reddit_rows():
    listing = {"data": {"children": [{"data": {"score": 10, "num_comments": 5}}, {"data": {"score": 1, "num_comments": 0}}]}}
    s = FakeSession([("access_token", 200, {"access_token": "T"}), ("/search", 200, listing),
                     ("/r/bluey/about", 200, {"data": {"subscribers": 4200}})])
    rows = reddit.collect(s, [SEED, GONE], "id", "secret", now=datetime(2026, 10, 10, tzinfo=timezone.utc))
    got = {(r.ip_id, r.metric): r.value for r in rows}
    assert got[("bluey", "posts_7d")] == 2 and got[("bluey", "engagement_7d")] == 16
    assert got[("bluey", "subscribers")] == 4200 and ("gone", "subscribers") not in got


class FakeTrends:
    def __init__(self, fail_terms=(), flaky_terms=()):
        self.fail_terms, self.term = fail_terms, None
        self.flaky = set(flaky_terms)  # 第一次失败、重试成功

    def build_payload(self, kw, timeframe, geo):
        assert geo == "US"
        self.term = kw[0]

    def interest_over_time(self):
        if self.term in self.fail_terms:
            raise RuntimeError("429")
        if self.term in self.flaky:
            self.flaky.discard(self.term)
            raise RuntimeError("429")
        idx = pd.to_datetime(["2026-09-20", "2026-09-27", "2026-10-04"])
        return pd.DataFrame({self.term: [40, 60, 70], "isPartial": [False, False, True]}, index=idx)


def test_trends_drops_partial_week_and_survives_failures():
    rows = trends.collect([SEED, GONE], pause=0, retry_wait=0, client=FakeTrends(fail_terms={"Gone"}))
    assert [(r.date, r.value) for r in rows] == [("2026-09-20", 40.0), ("2026-09-27", 60.0)]


def test_trends_retries_once_after_failure():
    rows = trends.collect([SEED], pause=0, retry_wait=0, client=FakeTrends(flaky_terms={SEED.search_term}))
    assert len(rows) == 2



def test_trends_client_skips_pytrends_retry():
    # pytrends 4.9.2 在 retries>0 时用 urllib3 2.x 已删除的 method_whitelist 参数，每次请求都会失败
    from unittest import mock
    from pytrends import request
    with mock.patch.object(request.TrendReq, "GetGoogleCookie", return_value={}):
        client = trends._client()
    assert client.retries == 0 and client.backoff_factor == 0


def bili_page(pubdates, play=10):
    return {"code": 0, "data": {"result": [{"pubdate": int(p.timestamp()), "play": play} for p in pubdates]}}


def test_bilibili_counts_last_7_days():
    from ipradar.collectors import bilibili
    now = datetime(2026, 10, 14, tzinfo=timezone.utc)
    page = bili_page([now - timedelta(days=1), now - timedelta(days=3), now - timedelta(days=9)])
    s = FakeSession([("search/type", 200, page), ("www.bilibili.com", 200, {})])
    rows = bilibili.collect(s, [SEED], now=now, pause=0)
    assert {(r.metric, r.value) for r in rows} == {("new_videos_7d", 2), ("views_7d", 20)}
    bad = FakeSession([("search/type", 200, {"code": -412, "message": "请求被拦截"})])
    assert bilibili.collect(bad, [SEED], now=now, pause=0) == []


def test_bilibili_backfill_keeps_only_fully_covered_weeks():
    from ipradar.collectors import bilibili
    now = datetime(2026, 10, 14, tzinfo=timezone.utc)  # 周三；本周从 10-12 开始
    # 一页 20 条都在 10-01（上上周四）之后，翻页没到底，所以只有完整覆盖的上周可用
    full = bili_page([datetime(2026, 10, 13, tzinfo=timezone.utc)] * 5 + [datetime(2026, 10, 6, tzinfo=timezone.utc)] * 14
                     + [datetime(2026, 10, 1, tzinfo=timezone.utc)])
    s = FakeSession([("search/type", 200, full)])
    assert bilibili.backfill_weeks(s, "x", now, weeks=4, max_pages=1, pause=0) == [(date(2026, 10, 11), 14)]
    # 翻到底（不足 20 条），4 周全部可用，没有视频的周记 0
    short = bili_page([datetime(2026, 10, 6, tzinfo=timezone.utc)] * 3 + [datetime(2026, 9, 22, tzinfo=timezone.utc)])
    s = FakeSession([("search/type", 200, short)])
    assert bilibili.backfill_weeks(s, "x", now, weeks=4, pause=0) == [
        (date(2026, 9, 20), 0), (date(2026, 9, 27), 1), (date(2026, 10, 4), 0), (date(2026, 10, 11), 3)]
