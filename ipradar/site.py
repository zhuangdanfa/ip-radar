"""生成网页看板：把 web/index.html 和最新数据 data.json 放进一个目录，由 GitHub Pages 发布。"""
from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

from ipradar.config import ROOT
from ipradar.report import SOURCE_ZH
from ipradar.score import IpScore, weekly_series
from ipradar.seeds import Seed
from ipradar.store import Row

TEMPLATE = ROOT / "web" / "index.html"
SITE_DIR = ROOT / "_site"
WEEKS = 52  # 看板上每个指标展示近一年的周数据

METRIC_ZH = {
    ("wikipedia", "pageviews"): "Wikipedia 周浏览量",
    ("trends", "interest"): "Google 搜索热度（美国，0–100）",
    ("youtube", "new_videos_7d"): "YouTube 近 7 天新视频数",
    ("youtube", "views_7d"): "YouTube 近 7 天热门视频播放量",
    ("reddit", "posts_7d"): "Reddit 近 7 天提及帖子数",
    ("reddit", "engagement_7d"): "Reddit 近 7 天互动量",
    ("reddit", "subscribers"): "Reddit 板块订阅数",
}


def build_payload(scores: list[IpScore], seeds: list[Seed], rows: list[Row], as_of: date) -> dict:
    by_id = {s.ip_id: s for s in seeds}
    series = weekly_series(rows, as_of)
    order = list(METRIC_ZH)
    rank_of = {s.ip_id: i for i, s in enumerate((s for s in scores if s.stage != "insufficient"), 1)}
    items = []
    for sc in scores:
        seed = by_id[sc.ip_id]
        charts = [{
            "source": src, "metric": m, "label": METRIC_ZH.get((src, m), f"{src} {m}"),
            "points": [[wk.isoformat(), round(v, 1)] for wk, v in s[-WEEKS:]],
        } for (ip, src, m), s in series.items() if ip == sc.ip_id and s]
        charts.sort(key=lambda c: order.index((c["source"], c["metric"])) if (c["source"], c["metric"]) in order else 99)
        items.append({
            "ip_id": sc.ip_id, "name_zh": seed.name_zh, "name_en": seed.name_en, "type": seed.type,
            "rank": rank_of.get(sc.ip_id),
            "momentum": sc.momentum, "stage": sc.stage, "stage_zh": sc.stage_zh,
            "growth_pct": round(sc.growth_pct, 1), "rising_sources": sc.rising_sources, "sources": sc.sources,
            "spark": [round(v, 1) for v in sc.spark], "charts": charts,
        })
    return {"as_of": as_of.isoformat(), "region": "北美", "source_names": SOURCE_ZH, "items": items}


def build_site(scores: list[IpScore], seeds: list[Seed], rows: list[Row], as_of: date,
               out_dir: Path = SITE_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(TEMPLATE, out_dir / "index.html")
    payload = build_payload(scores, seeds, rows, as_of)
    (out_dir / "data.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), "utf-8")
    return out_dir
