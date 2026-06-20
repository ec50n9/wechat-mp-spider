#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""微信公众号数据采集命令行工具。"""

import argparse
import json
from pathlib import Path

from wechat_mp_spider.analysis import generate_analysis_report
from wechat_mp_spider.auth import WechatAuthService
from wechat_mp_spider.config import DEFAULT_HEADLESS, OUTPUT_DIR
from wechat_mp_spider.spider import WechatSpider
from wechat_mp_spider.utils import create_run_output_dir, save_json


def load_json(path: str | Path):
    """读取 JSON 文件。"""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def print_sample(items) -> None:
    """打印一条样例，方便命令行快速确认结果。"""
    if items:
        sample = items[0] if isinstance(items, list) else items
        print(json.dumps(sample, ensure_ascii=False, indent=2)[:600])


def build_output_dir(args) -> Path:
    """创建本次命令的独立输出目录。"""
    output_root = Path(args.output_dir)
    run_output_dir = create_run_output_dir(output_root)
    print(f"[config] Playwright headless={args.headless}")
    print(f"[config] 本次输出目录: {run_output_dir}")
    return run_output_dir


def with_spider(args, handler):
    """启动认证上下文并执行具体抓取函数。"""
    run_output_dir = build_output_dir(args)
    with WechatAuthService(headless=args.headless) as auth:
        spider = WechatSpider(auth)
        return handler(spider, run_output_dir)


def crawl_publishes(args) -> None:
    """抓取发表记录。"""
    def handler(spider: WechatSpider, run_output_dir: Path):
        print("\n===== 抓取发表记录 =====")
        items = spider.fetch_publishes(max_pages=args.max_pages)
        print(f"[done] 共抓取 {len(items)} 条发表记录")
        if items:
            spider.save(items, run_output_dir, prefix="wechat_publishes")
            print_sample(items)

    with_spider(args, handler)


def crawl_fans(args) -> None:
    """抓取粉丝数据。"""
    def handler(spider: WechatSpider, run_output_dir: Path):
        print("\n===== 抓取粉丝数据 =====")
        summary = spider.fetch_fans_summary(args.start_date, args.end_date, debug_dir=run_output_dir)
        cumulate_user = summary.get("cumulate_user", [])
        total_fans = int(cumulate_user[-1]) if cumulate_user else None
        print(f"[done] 当前总粉丝数: {total_fans}")
        print(f"[done] 用户分析汇总: {summary.get('dates', [])}")
        spider.save([{"total_fans": total_fans}], run_output_dir, prefix="wechat_total_fans")
        spider.save(summary.get("raw", []), run_output_dir, prefix="wechat_fans_summary")
        save_json(summary, run_output_dir / "wechat_fans_summary_normalized.json")
        print(f"[spider] 归一化粉丝汇总已保存: {run_output_dir / 'wechat_fans_summary_normalized.json'}")

    with_spider(args, handler)


def resolve_publish_items(spider: WechatSpider, args) -> list[dict]:
    """按用户显式选择获取文章统计所需的发表记录。"""
    if args.publishes_file:
        print(f"[input] 读取发表记录文件: {args.publishes_file}")
        return load_json(args.publishes_file)
    if args.fetch_publishes:
        print("[input] 未提供发表记录文件，按 --fetch-publishes 临时抓取发表记录")
        return spider.fetch_publishes(max_pages=args.max_pages)
    raise SystemExit("抓取文章数据需要 --publishes-file，或显式添加 --fetch-publishes。")


def crawl_article_stats(args) -> None:
    """基于发表记录抓取/整理文章数据。"""
    def handler(spider: WechatSpider, run_output_dir: Path):
        print("\n===== 抓取文章数据 =====")
        publish_items = resolve_publish_items(spider, args)
        items = spider.batch_fetch_articles_stats(publish_items, include_public=args.include_public)
        print(f"[done] 共处理 {len(items)} 篇文章数据")
        if items:
            spider.save(items, run_output_dir, prefix="wechat_article_stats")
            print_sample(items)

    with_spider(args, handler)


def crawl_article_content(args) -> None:
    """按需抓取单篇文章正文。"""
    def handler(spider: WechatSpider, run_output_dir: Path):
        print("\n===== 按需抓取文章正文 =====")
        content = spider.fetch_article_content(args.url, include_html=args.include_html)
        save_json(content, run_output_dir / "wechat_article_content.json")
        print(f"[spider] 正文数据已保存: {run_output_dir / 'wechat_article_content.json'}")
        print_sample(content)

    with_spider(args, handler)


def generate_report(args) -> None:
    """基于已有数据文件生成分析报告，不触发爬取。"""
    run_output_dir = build_output_dir(args)
    article_stats = load_json(args.article_stats_file)
    fans_summary = load_json(args.fans_summary_file) if args.fans_summary_file else None
    total_fans = args.total_fans
    if total_fans is None and fans_summary:
        cumulate_user = fans_summary.get("cumulate_user", [])
        total_fans = int(cumulate_user[-1]) if cumulate_user else None

    report = generate_analysis_report(article_stats, fans_summary, total_fans)
    report_path = run_output_dir / "analysis.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"[analysis] 分析报告已保存: {report_path}")


def add_common_args(parser: argparse.ArgumentParser) -> None:
    """添加所有命令通用参数。"""
    parser.add_argument("--output-dir", default=OUTPUT_DIR, help="输出根目录，默认 output/")
    parser.add_argument(
        "--headless",
        default=DEFAULT_HEADLESS,
        action=argparse.BooleanOptionalAction,
        help="是否使用 headless 浏览器，默认读取 WECHAT_MP_HEADLESS",
    )


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="微信公众号后台数据采集工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    publishes = subparsers.add_parser("publishes", help="抓取发表记录")
    add_common_args(publishes)
    publishes.add_argument("--max-pages", type=int, default=None, help="最多抓取页数")
    publishes.set_defaults(func=crawl_publishes)

    fans = subparsers.add_parser("fans", help="抓取粉丝数据")
    add_common_args(fans)
    fans.add_argument("--start-date", default=None, help="开始日期 YYYY-MM-DD")
    fans.add_argument("--end-date", default=None, help="结束日期 YYYY-MM-DD")
    fans.set_defaults(func=crawl_fans)

    article_stats = subparsers.add_parser("article-stats", help="基于发表记录生成文章数据")
    add_common_args(article_stats)
    article_stats.add_argument("--publishes-file", default=None, help="已有 wechat_publishes_*.json 文件")
    article_stats.add_argument("--fetch-publishes", action="store_true", help="未传文件时显式临时抓取发表记录")
    article_stats.add_argument("--max-pages", type=int, default=None, help="配合 --fetch-publishes 使用，最多抓取页数")
    article_stats.add_argument("--include-public", action="store_true", help="额外访问公开正文页抓取公开阅读数")
    article_stats.set_defaults(func=crawl_article_stats)

    article_content = subparsers.add_parser("article-content", help="按需抓取单篇文章正文")
    add_common_args(article_content)
    article_content.add_argument("--url", required=True, help="文章正文 URL")
    article_content.add_argument("--include-html", action="store_true", help="额外保存正文 HTML")
    article_content.set_defaults(func=crawl_article_content)

    report = subparsers.add_parser("report", help="基于已有 JSON 生成分析报告")
    add_common_args(report)
    report.add_argument("--article-stats-file", required=True, help="wechat_article_stats_*.json 文件")
    report.add_argument("--fans-summary-file", default=None, help="wechat_fans_summary_normalized.json 文件")
    report.add_argument("--total-fans", type=int, default=None, help="当前总粉丝数")
    report.set_defaults(func=generate_report)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[exit] 用户中断")
    except Exception as e:
        print(f"\n[error] 运行异常: {e}")
        raise
