from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from ipradar.config import METRICS_FILE, REPORT_DIR
from ipradar.score import IpScore
from ipradar.seeds import Seed

BLOCKS = "▁▂▃▄▅▆▇█"
SOURCE_ZH = {"wikipedia": "Wikipedia", "trends": "Google Trends", "youtube": "YouTube", "reddit": "Reddit"}


def sparkline(values: list[float]) -> str:
    if not values:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    return "".join(BLOCKS[min(int((v - lo) / span * (len(BLOCKS) - 1) + 0.5), len(BLOCKS) - 1)] for v in values)


def render_markdown(scores: list[IpScore], seeds: list[Seed], as_of: date, top: int = 30) -> str:
    by_id = {s.ip_id: s for s in seeds}
    ranked = [s for s in scores if s.stage != "insufficient"]
    missing = [s for s in scores if s.stage == "insufficient"]
    lines = [
        f"# 北美 IP 上升榜 · {as_of.isoformat()}",
        "",
        f"共 {len(scores)} 个种子 IP，{len(ranked)} 个有足够数据（至少 8 周）参与排名。"
        "动量分 0–100 是在这批 IP 里的相对排名，看的是近 4 周相对前 4 周的增速、加速度和多平台同时上升的程度。",
        "",
        "| 排名 | IP | 类型 | 阶段 | 动量分 | 近 4 周变化 | 正在上升的数据源 | 近 12 周关注度 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for i, s in enumerate(ranked[:top], 1):
        seed = by_id[s.ip_id]
        rising = "、".join(SOURCE_ZH[x] for x in s.rising_sources) or "—"
        lines.append(f"| {i} | {seed.name_zh}（{seed.name_en}） | {seed.type} | {s.stage_zh} | {s.momentum} | "
                     f"{s.growth_pct:+.0f}% | {rising} | `{sparkline(s.spark)}` |")
    if missing:
        lines += ["", "**数据不足、暂不排名**：" + "、".join(by_id[s.ip_id].name_zh for s in missing)]
    lines += ["", "阶段规则：近 4 周增速超过约 22% 且关注度在这批 IP 的后一半为「萌芽」，前一半为「爆发」；"
              "增速低于约 −18% 为「衰退」；其余按关注度高低分为「成熟」和「平稳」。", ""]
    return "\n".join(lines)


def write_reports(scores: list[IpScore], seeds: list[Seed], as_of: date, out_dir: Path = REPORT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    md = out_dir / "latest.md"
    md.write_text(render_markdown(scores, seeds, as_of), "utf-8")
    payload = {
        "as_of": as_of.isoformat(),
        "scores": [{
            "ip_id": s.ip_id, "momentum": s.momentum, "stage": s.stage, "growth_pct": round(s.growth_pct, 1),
            "accel": round(s.accel, 3), "breadth": round(s.breadth, 2), "rising_sources": s.rising_sources,
            "sources": s.sources, "spark": [round(v, 1) for v in s.spark],
        } for s in scores],
    }
    (METRICS_FILE.parent / "scores_latest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), "utf-8")
    return md
