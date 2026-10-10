import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class FakeResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


class FakeSession:
    """按 URL 片段返回预设响应；记录每次请求，便于断言。"""

    def __init__(self, routes):
        self.routes = routes  # list of (url_substring, status, payload or callable(params))
        self.calls = []

    def _match(self, url, params):
        self.calls.append((url, params))
        for frag, status, payload in self.routes:
            if frag in url:
                return FakeResp(status, payload(params) if callable(payload) else payload)
        return FakeResp(404, {})

    def get(self, url, params=None, headers=None, timeout=None):
        return self._match(url, params)

    def post(self, url, auth=None, data=None, timeout=None):
        return self._match(url, data)
