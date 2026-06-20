#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试脚本：登录后只抓取 appmsgpublish 第一页，保存原始响应。
用于确认微信返回的是 JSON 还是 SSR 内嵌 JS 变量。
"""

from wechat_mp_spider.auth import WechatAuthService
from wechat_mp_spider.config import OUTPUT_DIR


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    with WechatAuthService(headless=False) as auth:
        auth.login()
        page = auth.page

        url = (
            "https://mp.weixin.qq.com/cgi-bin/appmsgpublish"
            f"?sub=list&begin=0&count=10&token={auth.token}&lang=zh_CN"
        )
        print(f"[step] 访问: {url}")
        page.goto(url, wait_until="networkidle", timeout=30_000)

        html = page.content()
        import time
        from pathlib import Path
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        debug_path = OUTPUT_DIR / f"debug_{timestamp}.html"
        debug_path.write_text(html, encoding="utf-8")
        print(f"[save] 原始响应已保存: {debug_path}")

        scripts = page.locator("script").all()
        print(f"[info] 页面共有 {len(scripts)} 个 <script> 标签")


if __name__ == "__main__":
    main()
