from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED_FILE = ROOT / "seeds" / "na_seed.csv"
METRICS_FILE = ROOT / "data" / "metrics.csv"
TITLE_CACHE_FILE = ROOT / "data" / "wikipedia_titles.json"
REPORT_DIR = ROOT / "reports"

USER_AGENT = "ip-radar/0.1 (trend research prototype; https://github.com/zhuangdanfa/ip-radar)"
REGION = "US"

# 每个指标按周汇总的方式：
#   sum  每日计数相加（如浏览量）
#   mean 指数取平均（如 Google Trends 0-100）
#   last 每日采集的是「近 7 天」滚动值，取本周最后一次
METRICS: dict[tuple[str, str], str] = {
    ("wikipedia", "pageviews"): "sum",
    ("trends", "interest"): "mean",
    ("youtube", "new_videos_7d"): "last",
    ("youtube", "views_7d"): "last",
    ("reddit", "posts_7d"): "last",
    ("reddit", "engagement_7d"): "last",
    ("reddit", "subscribers"): "last",
}
