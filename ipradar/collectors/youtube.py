"""YouTube 近 7 天新视频数和头部视频播放量（YouTube Data API v3，需要 YOUTUBE_API_KEY）。

配额：每个 IP 约 101 单位（search 100 + videos 1），免费额度每天 10,000 单位，约够 90 个 IP。
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from ipradar.config import REGION
from ipradar.http import HttpError, get_json
from ipradar.seeds import Seed
from ipradar.store import Row

log = logging.getLogger(__name__)

API = "https://www.googleapis.com/youtube/v3"


def fetch_week(session, api_key: str, term: str, now: datetime) -> tuple[int, int]:
    """返回 (近 7 天视频数估计, 近 7 天播放量前 50 视频的总播放量)。"""
    after = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    search = get_json(session, f"{API}/search", params={
        "key": api_key, "part": "id", "q": term, "type": "video", "order": "viewCount",
        "publishedAfter": after, "regionCode": REGION, "relevanceLanguage": "en", "maxResults": 50,
    })
    total = int(search.get("pageInfo", {}).get("totalResults", 0))
    ids = [it["id"]["videoId"] for it in search.get("items", []) if it.get("id", {}).get("videoId")]
    views = 0
    if ids:
        stats = get_json(session, f"{API}/videos", params={"key": api_key, "part": "statistics", "id": ",".join(ids)})
        views = sum(int(v.get("statistics", {}).get("viewCount", 0)) for v in stats.get("items", []))
    return total, views


def collect(session, seeds: list[Seed], api_key: str, now: datetime | None = None) -> list[Row]:
    now = now or datetime.now(timezone.utc)
    day = now.date().isoformat()
    rows: list[Row] = []
    for s in seeds:
        try:
            total, views = fetch_week(session, api_key, s.search_term, now)
        except HttpError as e:
            if e.status == 403:
                log.error("YouTube 返回 403（密钥无效或今日配额用完），停止本轮 YouTube 采集")
                break
            log.warning("YouTube 采集失败 %s：%s", s.ip_id, e)
            continue
        rows += [Row(day, s.ip_id, "youtube", "new_videos_7d", total),
                 Row(day, s.ip_id, "youtube", "views_7d", views)]
    return rows
