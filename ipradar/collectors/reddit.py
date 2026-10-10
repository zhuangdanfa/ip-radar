"""Reddit 近 7 天提及帖子数、互动量和相关板块订阅数（官方 API，需要 REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET）。

免费接口面向非商业用途；公司长期使用前需确认 Reddit 的数据使用条款。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from ipradar.http import HttpError, get_json
from ipradar.seeds import Seed
from ipradar.store import Row

log = logging.getLogger(__name__)

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
API = "https://oauth.reddit.com"


def get_token(session, client_id: str, client_secret: str) -> str:
    resp = session.post(TOKEN_URL, auth=(client_id, client_secret),
                        data={"grant_type": "client_credentials"}, timeout=30)
    if resp.status_code != 200:
        raise HttpError(resp.status_code, TOKEN_URL)
    return resp.json()["access_token"]


def fetch_mentions(session, headers: dict, term: str) -> tuple[int, int]:
    data = get_json(session, f"{API}/search", headers=headers, params={
        "q": f'"{term}"', "sort": "new", "t": "week", "limit": 100, "type": "link",
    })
    posts = [c["data"] for c in data.get("data", {}).get("children", [])]
    return len(posts), sum(int(p.get("score", 0)) + int(p.get("num_comments", 0)) for p in posts)


def fetch_subscribers(session, headers: dict, subreddit: str) -> int | None:
    try:
        data = get_json(session, f"{API}/r/{subreddit}/about", headers=headers)
    except HttpError as e:
        if e.status in (403, 404):  # 私密、被封或不存在的板块
            return None
        raise
    return data.get("data", {}).get("subscribers")


def collect(session, seeds: list[Seed], client_id: str, client_secret: str,
            now: datetime | None = None) -> list[Row]:
    day = (now or datetime.now(timezone.utc)).date().isoformat()
    headers = {"Authorization": f"bearer {get_token(session, client_id, client_secret)}"}
    rows: list[Row] = []
    for s in seeds:
        try:
            n, engagement = fetch_mentions(session, headers, s.search_term)
            rows += [Row(day, s.ip_id, "reddit", "posts_7d", n),
                     Row(day, s.ip_id, "reddit", "engagement_7d", engagement)]
            if s.subreddit:
                subs = fetch_subscribers(session, headers, s.subreddit)
                if subs is not None:
                    rows.append(Row(day, s.ip_id, "reddit", "subscribers", subs))
        except HttpError as e:
            log.warning("Reddit 采集失败 %s：%s", s.ip_id, e)
    return rows
