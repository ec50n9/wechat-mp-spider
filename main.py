#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""微信公众号数据采集命令行工具（基于 Typer）。"""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import typer

from wechat_mp_spider.analysis import generate_analysis_report
from wechat_mp_spider.auth import WechatAuthService
from wechat_mp_spider.config import DEFAULT_HEADLESS, OUTPUT_DIR
from wechat_mp_spider.spider import WechatSpider
from wechat_mp_spider.utils import create_run_output_dir, save_json


def load_json(path: str | Path):
    """读取 JSON 文件。"""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def print_json(data, compact: bool = False, sample: bool = False) -> None:
    """把数据作为 JSON 打印到 stdout。"""
    if data is None:
        return
    if compact:
        print(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        return

    text = json.dumps(data, ensure_ascii=False, indent=2)
    if sample:
        text = text[:600]
    print(text)


def build_output_dir(args) -> Path | None:
    """创建本次命令的独立输出目录，stdout 模式下不创建。"""
    if args.stdout:
        print(f"[config] Playwright headless={args.headless}")
        return None
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


def _crawl_publishes(args) -> None:
    """抓取发表记录。"""
    def handler(spider: WechatSpider, run_output_dir: Path | None):
        if not args.stdout:
            print("\n===== 抓取发表记录 =====")
        items = spider.fetch_publishes(max_pages=args.max_pages)
        if args.stdout:
            print_json(items)
            return
        print(f"[done] 共抓取 {len(items)} 条发表记录")
        if items:
            spider.save(items, run_output_dir, prefix="wechat_publishes")
            print_json(items[0] if isinstance(items, list) else items, sample=True)

    with_spider(args, handler)


def _crawl_fans(args) -> None:
    """抓取粉丝数据。"""
    def handler(spider: WechatSpider, run_output_dir: Path | None):
        if not args.stdout:
            print("\n===== 抓取粉丝数据 =====")
        summary = spider.fetch_fans_summary(
            args.start_date, args.end_date, debug_dir=run_output_dir
        )
        cumulate_user = summary.get("cumulate_user", [])
        total_fans = int(cumulate_user[-1]) if cumulate_user else None
        if args.stdout:
            print_json(summary)
            return
        print(f"[done] 当前总粉丝数: {total_fans}")
        print(f"[done] 用户分析汇总: {summary.get('dates', [])}")
        spider.save([{"total_fans": total_fans}], run_output_dir, prefix="wechat_total_fans")
        spider.save(summary.get("raw", []), run_output_dir, prefix="wechat_fans_summary")
        save_json(summary, run_output_dir / "wechat_fans_summary_normalized.json")
        print(f"[spider] 归一化粉丝汇总已保存: {run_output_dir / 'wechat_fans_summary_normalized.json'}")

    with_spider(args, handler)


def _resolve_publish_items(spider: WechatSpider, args) -> list[dict]:
    """按用户显式选择获取文章统计所需的发表记录。"""
    if args.publishes_file:
        if not args.stdout:
            print(f"[input] 读取发表记录文件: {args.publishes_file}")
        return load_json(args.publishes_file)
    if args.fetch_publishes:
        if not args.stdout:
            print("[input] 未提供发表记录文件，按 --fetch-publishes 临时抓取发表记录")
        return spider.fetch_publishes(max_pages=args.max_pages)
    raise SystemExit("抓取文章数据需要 --publishes-file，或显式添加 --fetch-publishes。")


def _crawl_article_stats(args) -> None:
    """基于发表记录抓取/整理文章数据。"""
    def handler(spider: WechatSpider, run_output_dir: Path | None):
        if not args.stdout:
            print("\n===== 抓取文章数据 =====")
        publish_items = _resolve_publish_items(spider, args)
        items = spider.batch_fetch_articles_stats(publish_items, include_public=args.include_public)
        if args.stdout:
            print_json(items)
            return
        print(f"[done] 共处理 {len(items)} 篇文章数据")
        if items:
            spider.save(items, run_output_dir, prefix="wechat_article_stats")
            print_json(items[0] if isinstance(items, list) else items, sample=True)

    with_spider(args, handler)


def _crawl_article_content(args) -> None:
    """按需抓取单篇文章正文。"""
    def handler(spider: WechatSpider, run_output_dir: Path | None):
        if not args.stdout:
            print("\n===== 按需抓取文章正文 =====")
        content = spider.fetch_article_content(args.url, include_html=args.include_html)
        if args.stdout:
            print_json(content)
            return
        save_json(content, run_output_dir / "wechat_article_content.json")
        print(f"[spider] 正文数据已保存: {run_output_dir / 'wechat_article_content.json'}")
        print_json(content, sample=True)

    with_spider(args, handler)


def _generate_report(args) -> None:
    """基于已有数据文件生成分析报告，不触发爬取。"""
    run_output_dir = build_output_dir(args)
    article_stats = load_json(args.article_stats_file)
    fans_summary = load_json(args.fans_summary_file) if args.fans_summary_file else None
    total_fans = args.total_fans
    if total_fans is None and fans_summary:
        cumulate_user = fans_summary.get("cumulate_user", [])
        total_fans = int(cumulate_user[-1]) if cumulate_user else None

    report = generate_analysis_report(article_stats, fans_summary, total_fans)
    if args.stdout:
        print(report)
        return
    report_path = run_output_dir / "analysis.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"[analysis] 分析报告已保存: {report_path}")


def _default_callback(ctx: typer.Context) -> None:
    """未提供子命令时友好地展示帮助信息并正常退出。"""
    if ctx.invoked_subcommand is None:
        print(ctx.get_help())
        raise typer.Exit(code=0)


app = typer.Typer(
    name="wechat-mp-spider",
    help="微信公众号后台数据采集工具",
    add_completion=False,
    callback=_default_callback,
    invoke_without_command=True,
)


_OUTPUT_DIR_OPTION = typer.Option(OUTPUT_DIR, "--output-dir", help="输出根目录，默认 output/")
_HEADLESS_OPTION = typer.Option(
    DEFAULT_HEADLESS,
    "--headless/--no-headless",
    help="是否使用 headless 浏览器，默认读取 WECHAT_MP_HEADLESS",
)
_STDOUT_OPTION = typer.Option(
    False,
    "--stdout",
    help="将结果直接输出到 stdout，不写入文件",
)


@app.command("publishes", help="抓取发表记录")
def crawl_publishes(
    output_dir: Path = _OUTPUT_DIR_OPTION,
    headless: bool = _HEADLESS_OPTION,
    stdout: bool = _STDOUT_OPTION,
    max_pages: Optional[int] = typer.Option(None, "--max-pages", help="最多抓取页数"),
) -> None:
    """抓取公众号后台的发表记录列表。"""
    args = SimpleNamespace(output_dir=output_dir, headless=headless, stdout=stdout, max_pages=max_pages)
    _crawl_publishes(args)


@app.command("fans", help="抓取粉丝数据")
def crawl_fans(
    output_dir: Path = _OUTPUT_DIR_OPTION,
    headless: bool = _HEADLESS_OPTION,
    stdout: bool = _STDOUT_OPTION,
    start_date: Optional[str] = typer.Option(None, "--start-date", help="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = typer.Option(None, "--end-date", help="结束日期 YYYY-MM-DD"),
) -> None:
    """抓取指定日期范围内的粉丝汇总数据。"""
    args = SimpleNamespace(
        output_dir=output_dir, headless=headless, stdout=stdout, start_date=start_date, end_date=end_date
    )
    _crawl_fans(args)


@app.command("article-stats", help="基于发表记录生成文章数据")
def crawl_article_stats(
    output_dir: Path = _OUTPUT_DIR_OPTION,
    headless: bool = _HEADLESS_OPTION,
    stdout: bool = _STDOUT_OPTION,
    publishes_file: Optional[str] = typer.Option(
        None, "--publishes-file", help="已有 wechat_publishes_*.json 文件"
    ),
    fetch_publishes: bool = typer.Option(
        False, "--fetch-publishes", help="未传文件时显式临时抓取发表记录"
    ),
    max_pages: Optional[int] = typer.Option(
        None, "--max-pages", help="配合 --fetch-publishes 使用，最多抓取页数"
    ),
    include_public: bool = typer.Option(
        False, "--include-public", help="额外访问公开正文页抓取公开阅读数"
    ),
) -> None:
    """基于发表记录批量抓取文章阅读量、点赞等统计数据。"""
    args = SimpleNamespace(
        output_dir=output_dir,
        headless=headless,
        stdout=stdout,
        publishes_file=publishes_file,
        fetch_publishes=fetch_publishes,
        max_pages=max_pages,
        include_public=include_public,
    )
    _crawl_article_stats(args)


@app.command("article-content", help="按需抓取单篇文章正文")
def crawl_article_content(
    output_dir: Path = _OUTPUT_DIR_OPTION,
    headless: bool = _HEADLESS_OPTION,
    stdout: bool = _STDOUT_OPTION,
    url: str = typer.Option(..., "--url", help="文章正文 URL"),
    include_html: bool = typer.Option(
        False, "--include-html", help="额外保存正文 HTML"
    ),
) -> None:
    """按需抓取单篇文章的完整正文内容。"""
    args = SimpleNamespace(
        output_dir=output_dir, headless=headless, stdout=stdout, url=url, include_html=include_html
    )
    _crawl_article_content(args)


@app.command("report", help="基于已有 JSON 生成分析报告")
def generate_report_cmd(
    output_dir: Path = _OUTPUT_DIR_OPTION,
    headless: bool = _HEADLESS_OPTION,
    stdout: bool = _STDOUT_OPTION,
    article_stats_file: str = typer.Option(
        ..., "--article-stats-file", help="wechat_article_stats_*.json 文件"
    ),
    fans_summary_file: Optional[str] = typer.Option(
        None, "--fans-summary-file", help="wechat_fans_summary_normalized.json 文件"
    ),
    total_fans: Optional[int] = typer.Option(None, "--total-fans", help="当前总粉丝数"),
) -> None:
    """基于已有抓取结果生成 Markdown 分析报告，不触发浏览器。"""
    args = SimpleNamespace(
        output_dir=output_dir,
        headless=headless,
        stdout=stdout,
        article_stats_file=article_stats_file,
        fans_summary_file=fans_summary_file,
        total_fans=total_fans,
    )
    _generate_report(args)


def main() -> None:
    app()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[exit] 用户中断")
    except Exception as e:
        print(f"\n[error] 运行异常: {e}")
        raise
