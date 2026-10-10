"""Google Trends 美国搜索热度（近 12 个月，每周一个点，0-100）。

Google 没有完全开放的官方接口，这里用非官方库 pytrends，可能被限速。
每次请求的 0-100 是在该次请求的时间窗口内归一化的，不同请求之间不可比，
所以每次都整段替换某个 IP 的历史，而不是逐日追加。
"""
from __future__ import annotations

import logging
import time

from ipradar.config import REGION
from ipradar.seeds import Seed
from ipradar.store import Row

log = logging.getLogger(__name__)


def _client():
    from pytrends.request import TrendReq  # 延迟导入：没装 pytrends 也能跑其他数据源
    return TrendReq(hl="en-US", tz=300, retries=2, backoff_factor=1.0)


def fetch_interest(client, term: str, timeframe: str = "today 12-m") -> list[tuple[str, float]]:
    client.build_payload([term], timeframe=timeframe, geo=REGION)
    df = client.interest_over_time()
    if df is None or df.empty or term not in df:
        return []
    if "isPartial" in df:
        df = df[~df["isPartial"].astype(bool)]
    return [(idx.strftime("%Y-%m-%d"), float(v)) for idx, v in df[term].items()]


def collect(seeds: list[Seed], pause: float = 5.0, client=None) -> list[Row]:
    client = client or _client()
    rows: list[Row] = []
    for i, s in enumerate(seeds):
        if i:
            time.sleep(pause)  # 放慢节奏，减少被限速
        try:
            for d, v in fetch_interest(client, s.search_term):
                rows.append(Row(d, s.ip_id, "trends", "interest", v))
        except Exception as e:  # pytrends 被限速时抛各种异常，不让一个 IP 拖垮整轮
            log.warning("Google Trends 采集失败 %s：%s", s.ip_id, e)
    return rows
