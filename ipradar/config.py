from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED_FILE = ROOT / "seeds" / "na_seed.csv"
METRICS_FILE = ROOT / "data" / "metrics.csv"
TITLE_CACHE_FILE = ROOT / "data" / "wikipedia_titles.json"
REPORT_DIR = ROOT / "reports"

USER_AGENT = "ip-radar/0.1 (trend research prototype; https://github.com/zhuangdanfa/ip-radar)"
REGION = "US"


@dataclass(frozen=True)
class Region:
    id: str
    name: str
    seed_file: Path
    data_dir: Path
    report_dir: Path
    sources: tuple[str, ...]

    @property
    def metrics_file(self) -> Path:
        return self.data_dir / "metrics.csv"


# 每个地区一份种子清单、一份数据和一份上升榜；北美沿用最初的路径
REGIONS: dict[str, Region] = {
    "na": Region("na", "北美", SEED_FILE, METRICS_FILE.parent, REPORT_DIR,
                 ("wikipedia", "trends", "youtube", "reddit")),
    "cn": Region("cn", "中国", ROOT / "seeds" / "cn_seed.csv", ROOT / "data" / "cn", REPORT_DIR / "cn",
                 ("bilibili",)),
}

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
    ("bilibili", "new_videos_7d"): "last",
    ("bilibili", "views_7d"): "last",
}
