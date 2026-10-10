from __future__ import annotations

import argparse
import logging
import os
from datetime import date, timedelta

from ipradar import score as scoring
from ipradar.http import make_session
from ipradar.report import write_reports
from ipradar.seeds import load_seeds
from ipradar.store import read_rows, upsert_rows

log = logging.getLogger("ipradar")
ALL_SOURCES = ["wikipedia", "trends", "youtube", "reddit"]


def cmd_collect(args) -> int:
    seeds = load_seeds()
    if args.only:
        seeds = [s for s in seeds if s.ip_id in set(args.only.split(","))]
    session = make_session()
    failed = []
    for source in args.sources.split(","):
        try:
            if source == "wikipedia":
                from ipradar.collectors import wikipedia
                n = upsert_rows(wikipedia.collect(session, seeds, days=args.days))
            elif source == "trends":
                from ipradar.collectors import trends
                n = upsert_rows(trends.collect(seeds), replace_series=True)
            elif source == "youtube":
                key = os.environ.get("YOUTUBE_API_KEY")
                if not key:
                    log.warning("没有设置 YOUTUBE_API_KEY，跳过 YouTube")
                    continue
                from ipradar.collectors import youtube
                n = upsert_rows(youtube.collect(session, seeds, key))
            elif source == "reddit":
                cid, secret = os.environ.get("REDDIT_CLIENT_ID"), os.environ.get("REDDIT_CLIENT_SECRET")
                if not (cid and secret):
                    log.warning("没有设置 REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET，跳过 Reddit")
                    continue
                from ipradar.collectors import reddit
                n = upsert_rows(reddit.collect(session, seeds, cid, secret))
            else:
                log.error("未知数据源：%s", source)
                failed.append(source)
                continue
            log.info("%s：写入 %d 行", source, n)
        except Exception:
            log.exception("%s 采集整体失败", source)
            failed.append(source)
    # 单个数据源失败不影响其他数据源；全部失败才返回错误
    return 1 if failed and len(failed) == len(args.sources.split(",")) else 0


def cmd_report(args) -> int:
    seeds = load_seeds()
    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    scores = scoring.score(read_rows(), [s.ip_id for s in seeds], as_of=as_of)
    path = write_reports(scores, seeds, as_of)
    names = {s.ip_id: s.name_zh for s in seeds}
    for i, s in enumerate([s for s in scores if s.stage != "insufficient"][:10], 1):
        print(f"{i:>2}. {names[s.ip_id]:<12} 动量 {s.momentum:>3}  {s.stage_zh}  近4周 {s.growth_pct:+.0f}%")
    print(f"报告已写入 {path}")
    return 0


def cmd_backtest(args) -> int:
    """看某个 IP 在过去每一周的排名，用来检验系统能提前多少周发现它。"""
    seeds = load_seeds()
    rows = read_rows()
    ids = [s.ip_id for s in seeds]
    if args.ip not in ids:
        log.error("种子列表里没有 %s", args.ip)
        return 1
    end = date.fromisoformat(args.end) if args.end else date.today()
    print("周（截至）     排名  动量  阶段    近4周变化")
    for k in range(args.weeks, -1, -1):
        as_of = scoring.week_start(end) - timedelta(days=7 * k) - timedelta(days=1)
        scores = scoring.score(rows, ids, as_of=as_of)
        ranked = [s for s in scores if s.stage != "insufficient"]
        hit = next((s for s in ranked if s.ip_id == args.ip), None)
        if hit is None:
            print(f"{as_of}   数据不足")
            continue
        print(f"{as_of}   {ranked.index(hit) + 1:>3}/{len(ranked):<3} {hit.momentum:>4}  {hit.stage_zh:<6} {hit.growth_pct:+.0f}%")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="ipradar", description="北美 IP 趋势雷达")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect", help="采集数据，写入 data/metrics.csv")
    c.add_argument("--sources", default=",".join(ALL_SOURCES))
    c.add_argument("--days", type=int, default=14, help="Wikipedia 回溯天数（首次可设 400 做回测）")
    c.add_argument("--only", help="只采集这些 ip_id，逗号分隔")
    c.set_defaults(func=cmd_collect)
    r = sub.add_parser("report", help="计算动量分并生成 reports/latest.md")
    r.add_argument("--as-of", help="按某天为截止日计算，YYYY-MM-DD")
    r.set_defaults(func=cmd_report)
    b = sub.add_parser("backtest", help="查看某个 IP 过去每周的排名")
    b.add_argument("ip")
    b.add_argument("--weeks", type=int, default=26)
    b.add_argument("--end", help="截止日 YYYY-MM-DD，默认今天")
    b.set_defaults(func=cmd_backtest)
    args = p.parse_args(argv)
    return args.func(args)
