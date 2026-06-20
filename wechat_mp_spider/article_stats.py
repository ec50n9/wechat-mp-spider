"""
单篇文章阅读数据抓取。

数据来源：公众号后台「内容分析」或「单篇群发」页面。
可以通过 appmsgid 或内容链接定位文章，读取其阅读量、分享量、完成阅读率等。
"""

import json
import re
import time
from datetime import datetime
from typing import Any

from wechat_mp_spider.config import DEFAULT_PAGE_TIMEOUT
from wechat_mp_spider.exceptions import FetchError


class ArticleStatsFetcher:
    """单篇文章阅读数据获取器。"""

    def __init__(self, auth, page_timeout: int = DEFAULT_PAGE_TIMEOUT):
        self.auth = auth
        self.page_timeout = page_timeout

    def fetch_article_stats_by_appmsgid(
        self,
        appmsgid: int | str,
        itemidx: int = 1,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """
        根据 appmsgid 抓取单篇文章的阅读数据。

        访问链接示例：
        https://mp.weixin.qq.com/cgi-bin/appmsg?
            t=media/appmsg_edit_v2&action=edit&isNew=1&appmsgid=xxx&token=xxx&lang=zh_CN
        """
        token = self.auth.ensure_token()
        page = self.auth.page

        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if start_date is None:
            # 默认抓取最近 30 天
            start_date = (datetime.now() - __import__("datetime").timedelta(days=30)).strftime("%Y-%m-%d")

        url = (
            "https://mp.weixin.qq.com/cgi-bin/appmsg"
            f"?t=media/appmsg_edit_v2&action=edit&isNew=1"
            f"&appmsgid={appmsgid}&itemidx={itemidx}"
            f"&token={token}&lang=zh_CN"
        )
        print(f"[article] 访问文章编辑页: {url}")
        page.goto(url, wait_until="networkidle", timeout=self.page_timeout)
        page.wait_for_timeout(3000)

        html = page.content()

        # 尝试从页面变量中读取文章数据
        patterns = [
            r"window\.__INITIAL_STATE__\s*=\s*(\{[\s\S]*?\});",
            r"var\s+appmsgData\s*=\s*(\{[\s\S]*?\});",
            r"var\s+initData\s*=\s*(\{[\s\S]*?\});",
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                try:
                    data = json.loads(match.group(1))
                    return {
                        "appmsgid": appmsgid,
                        "itemidx": itemidx,
                        "source": "edit_page",
                        "data": data,
                    }
                except json.JSONDecodeError:
                    continue

        raise FetchError(f"无法从文章编辑页提取数据: appmsgid={appmsgid}")

    def fetch_article_stats_from_content_url(
        self,
        content_url: str,
        wait_ms: int = 5000,
    ) -> dict:
        """
        通过文章正文链接抓取公开阅读数据（阅读量、点赞量、在看数等）。

        注意：公开页面只能拿到少量数据，且受微信反爬限制。
        """
        token = self.auth.ensure_token()
        page = self.auth.page

        print(f"[article] 访问文章正文: {content_url}")
        page.goto(content_url, wait_until="networkidle", timeout=self.page_timeout)
        page.wait_for_timeout(wait_ms)

        # 提取阅读量、点赞量等
        result = {
            "content_url": content_url,
            "source": "public_page",
            "read_num": None,
            "like_num": None,
            "old_like_num": None,
        }

        # 微信公开文章数据通常在 #js_read_area3 / #like_area / #old_like_area
        selectors = {
            "read_num": "#js_read_area3",
            "like_num": "#like_area .weui-like__num",
            "old_like_num": "#old_like_area .weui-like__num",
        }
        for key, selector in selectors.items():
            try:
                el = page.locator(selector).first
                if el.is_visible():
                    text = el.inner_text().strip()
                    digits = "".join(c for c in text if c.isdigit())
                    if digits:
                        result[key] = int(digits)
            except Exception:
                continue

        # 标题
        try:
            result["title"] = page.locator("#activity_name").first.inner_text().strip()
        except Exception:
            result["title"] = None

        return result

    def fetch_article_content_from_content_url(
        self,
        content_url: str,
        wait_ms: int = 5000,
        include_html: bool = False,
    ) -> dict:
        """
        按需抓取文章正文内容。

        默认只返回正文纯文本和页面元数据；include_html=True 时额外返回正文 HTML，
        适合后续需要分析文章结构、图片位置或排版时单篇调用。
        """
        self.auth.ensure_token()
        page = self.auth.page

        print(f"[article] 按需采集文章正文: {content_url}")
        page.goto(content_url, wait_until="networkidle", timeout=self.page_timeout)
        page.wait_for_timeout(wait_ms)

        def first_text(selectors: list[str]) -> str | None:
            for selector in selectors:
                try:
                    text = page.locator(selector).first.inner_text().strip()
                    if text:
                        return text
                except Exception:
                    continue
            return None

        def first_attr(selectors: list[str], attr: str) -> str | None:
            for selector in selectors:
                try:
                    value = page.locator(selector).first.get_attribute(attr)
                    if value:
                        return value
                except Exception:
                    continue
            return None

        content_text = first_text(["#js_content", ".rich_media_content"])
        content_html = None
        if include_html:
            try:
                content_html = page.locator("#js_content").first.inner_html()
            except Exception:
                content_html = None

        image_count = 0
        try:
            image_count = page.locator("#js_content img").count()
        except Exception:
            pass

        result = {
            "content_url": content_url,
            "source": "content_page",
            "title": first_text(["#activity-name", "#activity_name", ".rich_media_title"]),
            "author": first_text(["#js_name", ".rich_media_meta_text.rich_media_meta_nickname"]),
            "publish_time_text": first_text(["#publish_time", "#js_publish_time"]),
            "digest": first_attr(['meta[name="description"]', 'meta[property="og:description"]'], "content"),
            "cover": first_attr(['meta[property="og:image"]', 'meta[name="twitter:image"]'], "content"),
            "content_text": content_text,
            "content_length": len(content_text or ""),
            "image_count": image_count,
        }
        if include_html:
            result["content_html"] = content_html
        return result

    @staticmethod
    def _extract_article_metadata(appmsg: dict[str, Any]) -> dict:
        """从发表记录 appmsg_info 中提取影响阅读表现的文章元数据。"""
        title = appmsg.get("title") or ""
        digest = appmsg.get("digest") or ""
        cover = appmsg.get("cover") or ""
        cover_16_9 = appmsg.get("pic_cdn_url_16_9") or ""
        cover_235_1 = appmsg.get("pic_cdn_url_235_1") or ""
        return {
            "title": title,
            "title_length": len(title),
            "digest": digest,
            "digest_length": len(digest),
            "author": appmsg.get("author"),
            "cover": cover,
            "cover_16_9": cover_16_9,
            "cover_235_1": cover_235_1,
            "has_cover": bool(cover or cover_16_9 or cover_235_1),
            "source_url": appmsg.get("source_url"),
            "copyright_status": appmsg.get("copyright_status"),
            "copyright_type": appmsg.get("copyright_type"),
            "share_num": appmsg.get("share_num"),
            "comment_num": appmsg.get("comment_num"),
            "reprint_num": appmsg.get("reprint_num"),
            "moment_like_num": appmsg.get("moment_like_num"),
            "multi_picture_cover": appmsg.get("multi_picture_cover"),
        }

    def fetch_all_articles_stats(
        self,
        publish_items: list[dict],
        include_public: bool = False,
    ) -> list[dict]:
        """
        基于发表记录批量抓取每篇文章的阅读数据。

        Args:
            publish_items: fetch_publishes() 返回的发表记录列表
            include_public: 是否额外访问公开正文页抓取阅读数（较慢）
        """
        results = []
        for item in publish_items:
            publish_info = item.get("publish_info", {})
            if not isinstance(publish_info, dict):
                continue

            appmsg_info_raw = publish_info.get("appmsg_info", [])
            # 兼容单篇文章时 appmsg_info 是 dict 而非 list 的情况
            appmsg_info_list = appmsg_info_raw if isinstance(appmsg_info_raw, list) else [appmsg_info_raw]
            for appmsg in appmsg_info_list:
                appmsgid = appmsg.get("appmsgid")
                itemidx = appmsg.get("itemidx", 1)
                content_url = appmsg.get("content_url")

                record = {
                    "appmsgid": appmsgid,
                    "itemidx": itemidx,
                    "content_url": content_url,
                    "publish_time": publish_info.get("sent_info", {}).get("time"),
                    "read_num": appmsg.get("read_num"),
                    "like_num": appmsg.get("like_num"),
                    "old_like_num": appmsg.get("old_like_num"),
                    **self._extract_article_metadata(appmsg),
                }

                if include_public and content_url:
                    try:
                        public_stats = self.fetch_article_stats_from_content_url(content_url)
                        record["public_read_num"] = public_stats.get("read_num")
                        record["public_like_num"] = public_stats.get("like_num")
                    except Exception as e:
                        print(f"[article] 公开页抓取失败 {content_url}: {e}")

                results.append(record)

        return results
