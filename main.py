#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""微信公众号数据采集入口脚本。"""

import json

from wechat_mp_spider.auth import WechatAuthService
from wechat_mp_spider.config import DEFAULT_HEADLESS, OUTPUT_DIR
from wechat_mp_spider.spider import WechatSpider
from wechat_mp_spider.utils import create_run_output_dir


def main():
    run_output_dir = create_run_output_dir(OUTPUT_DIR)

    print(f"[config] Playwright headless={DEFAULT_HEADLESS}")
    print(f"[config] 本次输出目录: {run_output_dir}")

    with WechatAuthService(headless=DEFAULT_HEADLESS) as auth:
        spider = WechatSpider(auth)

        # 1. 抓取发表记录
        print("\n===== 抓取发表记录 =====")
        publish_items = spider.fetch_publishes()
        print(f"[done] 共抓取 {len(publish_items)} 条发表记录")
        if publish_items:
            spider.save(publish_items, run_output_dir, prefix="wechat_publishes")
            print(json.dumps(publish_items[0], ensure_ascii=False, indent=2)[:600])

        # 2. 抓取总粉丝数
        print("\n===== 抓取总粉丝数 =====")
        try:
            total_fans = spider.fetch_total_fans()
            print(f"[done] 当前总粉丝数: {total_fans}")
        except Exception as e:
            print(f"[error] 抓取总粉丝数失败: {e}")

        # 3. 抓取用户分析汇总（最近 7 天）
        print("\n===== 抓取用户分析汇总 =====")
        try:
            fans_summary = spider.fetch_fans_summary()
            print(f"[done] 用户分析汇总: {fans_summary.get('dates', [])}")
            print(f"[done] 新增用户: {fans_summary.get('new_user', [])}")
            print(f"[done] 净增用户: {fans_summary.get('net_gain', [])}")
            print(f"[done] 累计用户: {fans_summary.get('cumulate_user', [])}")
        except Exception as e:
            print(f"[error] 抓取用户分析汇总失败: {e}")

        # 4. 批量抓取单篇文章阅读数据
        print("\n===== 批量抓取文章阅读数据 =====")
        try:
            article_stats = spider.batch_fetch_articles_stats(publish_items, include_public=False)
            print(f"[done] 共抓取 {len(article_stats)} 篇文章数据")
            if article_stats:
                spider.save(article_stats, run_output_dir, prefix="wechat_article_stats")
                print(json.dumps(article_stats[0], ensure_ascii=False, indent=2)[:600])
        except Exception as e:
            print(f"[error] 批量抓取文章阅读数据失败: {e}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[exit] 用户中断")
    except Exception as e:
        print(f"\n[error] 运行异常: {e}")
        raise
