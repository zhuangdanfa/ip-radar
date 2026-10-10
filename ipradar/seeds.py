from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from ipradar.config import SEED_FILE


@dataclass(frozen=True)
class Seed:
    ip_id: str
    name_zh: str
    name_en: str
    type: str
    wikipedia_title: str
    search_term: str
    subreddit: str


def load_seeds(path: Path = SEED_FILE) -> list[Seed]:
    with path.open(encoding="utf-8", newline="") as f:
        seeds = [Seed(**{k: (v or "").strip() for k, v in row.items()}) for row in csv.DictReader(f)]
    ids = [s.ip_id for s in seeds]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"种子列表里有重复的 ip_id：{sorted(dupes)}")
    return seeds
