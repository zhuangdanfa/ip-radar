"""B站近 7 天相关视频数和这些视频的总播放量（B站网页搜索的公开接口，不需要密钥）。

按发布时间倒序翻页，数到 7 天前为止。每页 20 条，最多翻 max_pages 页，
所以特别热门的 IP 会被截在 20 × max_pages 条，看的是趋势，不影响同一 IP 前后比较。

回填：B站搜索最多翻 50 页（1000 条），可以按发布时间倒推过去几周每周的新视频数，
这样不用等 8 周才有排名。只保留翻页完整覆盖到的周；播放量是累计值，旧视频天然更高，不回填。
"""
from __future__ import annotations

import logging
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from ipradar.http import get_json
from ipradar.seeds import Seed
from ipradar.store import Row

log = logging.getLogger(__name__)

HOME = "https://www.bilibili.com/"
SEARCH = "https://api.bilibili.com/x/web-interface/search/type"
# B站接口会拒绝非浏览器的 User-Agent
BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
HEADERS = {"User-Agent": BROWSER_UA, "Referer": "https://search.bilibili.com/"}


class BilibiliError(RuntimeError):
    pass


def _search_page(session, term: str, page: int) -> list[dict]:
    data = get_json(session, SEARCH, params={
        "search_type": "video", "keyword": term, "order": "pubdate", "page": page,
    }, headers=HEADERS)
    if data.get("code") != 0:
        raise BilibiliError(f"code={data.get('code')} {data.get('message')}")
    return (data.get("data") or {}).get("result") or []


def fetch_week(session, term: str, now: datetime, max_pages: int = 10, pause: float = 1.0) -> tuple[int, int]:
    """返回 (近 7 天视频数, 这些视频的总播放量)。"""
    cutoff = (now - timedelta(days=7)).timestamp()
    count = views = 0
    for page in range(1, max_pages + 1):
        if page > 1:
            time.sleep(pause)
        result = _search_page(session, term, page)
        for v in result:
            if v.get("pubdate", 0) < cutoff:
                return count, views
            count += 1
            views += int(v.get("play") or 0)
        if len(result) < 20:
            break
    return count, views


def backfill_weeks(session, term: str, now: datetime, weeks: int, max_pages: int = 50,
                   pause: float = 1.0) -> list[tuple[date, int]]:
    """返回过去 weeks 个完整自然周（周一到周日）每周的新视频数，按周日日期标记。"""
    this_monday = now.date() - timedelta(days=now.date().weekday())
    first_monday = this_monday - timedelta(weeks=weeks)
    counts: Counter[date] = Counter()
    oldest: date | None = None
    complete = False
    for page in range(1, max_pages + 1):
        if page > 1:
            time.sleep(pause)
        result = _search_page(session, term, page)
        for v in result:
            d = datetime.fromtimestamp(v.get("pubdate", 0), timezone.utc).date()
            if d < first_monday:
                complete = True
                break
            oldest = d
            if d < this_monday:
                counts[d - timedelta(days=d.weekday())] += 1
        if complete or len(result) < 20:
            complete = True
            break
    if not complete and oldest is None:
        return []
    # 没翻到底时，最旧那一周可能只数了一部分，从下一周开始算
    start = first_monday if complete else oldest - timedelta(days=oldest.weekday()) + timedelta(weeks=1)
    out = []
    wk = start
    while wk < this_monday:
        out.append((wk + timedelta(days=6), counts[wk]))
        wk += timedelta(weeks=1)
    return out


def collect(session, seeds: list[Seed], now: datetime | None = None, pause: float = 2.0,
            backfill: int = 0) -> list[Row]:
    """backfill > 0 时，先回填过去 backfill 周的每周新视频数。"""
    now = now or datetime.now(timezone.utc)
    day = now.date().isoformat()
    try:
        session.get(HOME, headers={"User-Agent": BROWSER_UA}, timeout=30)  # 拿到访客 cookie，搜索接口需要
    except Exception as e:
        log.warning("B站首页访问失败：%s", e)
    rows: list[Row] = []
    for i, s in enumerate(seeds):
        if i:
            time.sleep(pause)
        try:
            if backfill:
                rows += [Row(d.isoformat(), s.ip_id, "bilibili", "new_videos_7d", n)
                         for d, n in backfill_weeks(session, s.search_term, now, backfill, pause=pause / 2)]
            count, views = fetch_week(session, s.search_term, now, pause=pause / 2)
        except Exception as e:
            log.warning("B站采集失败 %s：%s", s.ip_id, e)
            continue
        rows += [Row(day, s.ip_id, "bilibili", "new_videos_7d", count),
                 Row(day, s.ip_id, "bilibili", "views_7d", views)]
    return rows
