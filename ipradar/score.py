"""动量分：看一个 IP 的关注度是否在加速上升、是否多个平台同时上升。

对每个 (IP, 数据源, 指标) 的周序列：
  增速 g    = log(近 4 周均值) − log(前 4 周均值)，需要至少 8 周数据
  加速度 a  = 本期 g − 4 周前的 g，需要至少 12 周数据，不足记 0
对每个 IP：
  G = 各指标 g 的平均，A = 各指标 a 的平均
  广度 B = 有指标增速超过 10% 的数据源占比
  原始分 = 0.45·G + 0.25·A + 0.30·B，再按全部 IP 的排名换算成 0–100 的动量分
权重是初始值，回测后再调。
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import mean

from ipradar.config import METRICS
from ipradar.store import Row

W_GROWTH, W_ACCEL, W_BREADTH = 0.45, 0.25, 0.30
RISING = 0.10  # 增速超过约 10% 算「在上升」
STAGE_ZH = {"emerging": "萌芽", "breakout": "爆发", "mature": "成熟", "declining": "衰退", "steady": "平稳",
            "insufficient": "数据不足"}


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def weekly_series(rows: list[Row], as_of: date | None = None) -> dict[tuple[str, str, str], list[tuple[date, float]]]:
    """按周汇总。按日相加的指标只保留 7 天齐全的周，避免不完整的一周看起来像下跌。"""
    buckets: dict[tuple[str, str, str], dict[date, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        d = date.fromisoformat(r.date)
        if as_of and d > as_of:
            continue
        buckets[(r.ip_id, r.source, r.metric)][week_start(d)].append(r.value)
    out = {}
    for key, weeks in buckets.items():
        mode = METRICS.get((key[1], key[2]), "mean")
        series = []
        for wk in sorted(weeks):
            vals = weeks[wk]
            if mode == "sum":
                if len(vals) < 7:
                    continue
                series.append((wk, sum(vals)))
            elif mode == "last":
                series.append((wk, vals[-1]))
            else:
                series.append((wk, mean(vals)))
        out[key] = series
    return out


def _log_mean(vals: list[float]) -> float:
    return math.log1p(max(mean(vals), 0.0))


def metric_signal(values: list[float]) -> tuple[float, float] | None:
    """返回 (增速 g, 加速度 a)；不足 8 周返回 None。"""
    if len(values) < 8:
        return None
    g = _log_mean(values[-4:]) - _log_mean(values[-8:-4])
    a = 0.0
    if len(values) >= 12:
        a = g - (_log_mean(values[-8:-4]) - _log_mean(values[-12:-8]))
    return g, a


@dataclass
class IpScore:
    ip_id: str
    momentum: int = 0
    raw: float = 0.0
    growth: float = 0.0
    accel: float = 0.0
    breadth: float = 0.0
    rising_sources: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    level: float = 0.0
    stage: str = "insufficient"
    spark: list[float] = field(default_factory=list)

    @property
    def stage_zh(self) -> str:
        return STAGE_ZH[self.stage]

    @property
    def growth_pct(self) -> float:
        return math.expm1(self.growth) * 100


def _percentile_ranks(values: list[float]) -> list[float]:
    if len(values) == 1:
        return [0.5]
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    for pos, i in enumerate(order):
        ranks[i] = pos / (len(values) - 1)
    return ranks


def score(rows: list[Row], ip_ids: list[str], as_of: date | None = None) -> list[IpScore]:
    series = weekly_series(rows, as_of)
    results: list[IpScore] = []
    for ip in ip_ids:
        sc = IpScore(ip)
        gs, accs, src_rising, srcs = [], [], set(), set()
        for (sid, source, metric), s in series.items():
            if sid != ip:
                continue
            sig = metric_signal([v for _, v in s])
            if sig is None:
                continue
            g, a = sig
            gs.append(g)
            accs.append(a)
            srcs.add(source)
            if g > RISING:
                src_rising.add(source)
        attention = series.get((ip, "wikipedia", "pageviews")) or series.get((ip, "trends", "interest")) or []
        sc.spark = [v for _, v in attention[-12:]]
        if gs:
            sc.growth, sc.accel = mean(gs), mean(accs)
            sc.sources, sc.rising_sources = sorted(srcs), sorted(src_rising)
            sc.breadth = len(src_rising) / len(srcs)
            sc.raw = W_GROWTH * sc.growth + W_ACCEL * sc.accel + W_BREADTH * sc.breadth
            sc.level = mean(v for _, v in attention[-4:]) if attention else 0.0
            sc.stage = "steady"
        results.append(sc)

    scored = [r for r in results if r.stage != "insufficient"]
    for r, pr in zip(scored, _percentile_ranks([r.raw for r in scored])):
        r.momentum = round(pr * 100)
    for r, lp in zip(scored, _percentile_ranks([r.level for r in scored])):
        r.stage = _stage(r.growth, lp)
    results.sort(key=lambda r: (r.stage != "insufficient", r.momentum), reverse=True)
    return results


def _stage(growth: float, level_pct: float) -> str:
    """按增速和关注度水平（在全部 IP 中的分位）判定生命周期阶段。"""
    if growth > 0.2:
        return "breakout" if level_pct >= 0.5 else "emerging"
    if growth < -0.2:
        return "declining"
    return "mature" if level_pct >= 0.5 else "steady"
