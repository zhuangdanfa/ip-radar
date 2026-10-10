"""英文 Wikipedia 每日浏览量（Wikimedia Pageviews API，免费、无需密钥，可回溯到 2015 年）。

浏览量是全球英文读者，不只是美国，但北美占比最高，作为「关注度基线」使用。
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

from ipradar.config import TITLE_CACHE_FILE
from ipradar.http import HttpError, get_json
from ipradar.seeds import Seed
from ipradar.store import Row

log = logging.getLogger(__name__)

API_QUERY = "https://en.wikipedia.org/w/api.php"
API_PAGEVIEWS = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
                 "en.wikipedia/all-access/user/{title}/daily/{start}/{end}")


def resolve_titles(session, titles: list[str], cache_path: Path = TITLE_CACHE_FILE) -> dict[str, str | None]:
    """把种子里的标题解析成规范标题（跟随重定向）。

    Pageviews API 不跟随重定向，查重定向页只会得到很小的数，所以必须先解析。
    不存在的条目映射为 None。结果缓存在 data/wikipedia_titles.json。
    """
    cache: dict[str, str | None] = json.loads(cache_path.read_text("utf-8")) if cache_path.exists() else {}
    todo = [t for t in titles if t and t not in cache]
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        data = get_json(session, API_QUERY, params={
            "action": "query", "titles": "|".join(t.replace("_", " ") for t in batch),
            "redirects": 1, "format": "json", "formatversion": 2,
        })
        q = data.get("query", {})
        step = {t.replace("_", " "): t.replace("_", " ") for t in batch}
        for n in q.get("normalized", []):
            for k, v in step.items():
                if v == n["from"]:
                    step[k] = n["to"]
        for r in q.get("redirects", []):
            for k, v in step.items():
                if v == r["from"]:
                    step[k] = r["to"]
        missing = {p["title"] for p in q.get("pages", []) if p.get("missing") or p.get("invalid")}
        for t in batch:
            final = step[t.replace("_", " ")]
            cache[t] = None if final in missing else final.replace(" ", "_")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True), "utf-8")
    return {t: cache.get(t) for t in titles}


def fetch_pageviews(session, title: str, start: date, end: date) -> list[tuple[str, int]]:
    url = API_PAGEVIEWS.format(title=quote(title, safe=""), start=start.strftime("%Y%m%d"),
                               end=end.strftime("%Y%m%d"))
    try:
        data = get_json(session, url)
    except HttpError as e:
        if e.status == 404:  # 该时间段没有数据
            return []
        raise
    out = []
    for item in data.get("items", []):
        ts = item["timestamp"]
        out.append((f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}", int(item["views"])))
    return out


def collect(session, seeds: list[Seed], days: int, today: date | None = None) -> list[Row]:
    end = (today or date.today()) - timedelta(days=1)  # 当天数据要第二天才完整
    start = end - timedelta(days=days - 1)
    canonical = resolve_titles(session, [s.wikipedia_title for s in seeds])
    rows: list[Row] = []
    for s in seeds:
        title = canonical.get(s.wikipedia_title)
        if not title:
            log.warning("Wikipedia 找不到条目，跳过：%s（%s）", s.ip_id, s.wikipedia_title)
            continue
        try:
            for d, views in fetch_pageviews(session, title, start, end):
                rows.append(Row(d, s.ip_id, "wikipedia", "pageviews", views))
        except HttpError as e:
            log.warning("Wikipedia 采集失败 %s：%s", s.ip_id, e)
    return rows
