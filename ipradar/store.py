"""指标存成一张长表 data/metrics.csv：date, ip_id, source, metric, value。

同一 (date, ip_id, source, metric) 重复写入时以新值为准，所以采集可以安全重跑。
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, NamedTuple

from ipradar.config import METRICS_FILE

FIELDS = ["date", "ip_id", "source", "metric", "value"]


class Row(NamedTuple):
    date: str  # YYYY-MM-DD
    ip_id: str
    source: str
    metric: str
    value: float


def read_rows(path: Path = METRICS_FILE) -> list[Row]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return [Row(r["date"], r["ip_id"], r["source"], r["metric"], float(r["value"])) for r in csv.DictReader(f)]


def upsert_rows(new_rows: Iterable[Row], path: Path = METRICS_FILE, replace_series: bool = False) -> int:
    """写入新数据。replace_series=True 时，新数据涉及的 (ip_id, source, metric) 先整段删掉再写入。"""
    new_rows = list(new_rows)
    drop = {(r.ip_id, r.source, r.metric) for r in new_rows} if replace_series else set()
    merged = {(r.date, r.ip_id, r.source, r.metric): r for r in read_rows(path)
              if (r.ip_id, r.source, r.metric) not in drop}
    count = 0
    for r in new_rows:
        merged[(r.date, r.ip_id, r.source, r.metric)] = r
        count += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        for key in sorted(merged):
            r = merged[key]
            w.writerow([r.date, r.ip_id, r.source, r.metric, f"{r.value:g}"])
    return count
