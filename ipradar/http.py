from __future__ import annotations

import logging
import time

import requests

from ipradar.config import USER_AGENT

log = logging.getLogger(__name__)


class HttpError(RuntimeError):
    def __init__(self, status: int, url: str):
        super().__init__(f"HTTP {status}: {url}")
        self.status = status


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def get_json(session, url: str, params: dict | None = None, headers: dict | None = None,
             retries: int = 3, backoff: float = 2.0) -> dict:
    """GET 并解析 JSON；429 和 5xx 按指数退避重试，其余错误直接抛出。"""
    for attempt in range(retries + 1):
        resp = session.get(url, params=params, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
            wait = backoff * (2 ** attempt)
            log.warning("HTTP %s，%.0f 秒后重试：%s", resp.status_code, wait, url)
            time.sleep(wait)
            continue
        raise HttpError(resp.status_code, url)
    raise AssertionError("unreachable")
