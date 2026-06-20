"""
微信后台数据爬虫。

职责：
- 基于已认证的 WechatAuthService 执行具体数据抓取
- 提供发表记录、粉丝数据、单篇文章数据等抓取能力
- 处理翻页、限流、异常重试
"""

import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from wechat_mp_spider.article_stats import ArticleStatsFetcher
from wechat_mp_spider.auth import WechatAuthService
from wechat_mp_spider.config import (
    DEFAULT_PAGE_SIZE,
    DEFAULT_PAGE_TIMEOUT,
    DEFAULT_SLEEP_BETWEEN_PAGES,
)
from wechat_mp_spider.drafts import DraftsManager
from wechat_mp_spider.exceptions import CookieExpiredError, FetchError
from wechat_mp_spider.fans import FansDataFetcher
from wechat_mp_spider.parser import PublishPageParser
from wechat_mp_spider.utils import save_csv, save_json


class WechatSpider:
    """微信后台数据爬虫。"""

    def __init__(
        self,
        auth: WechatAuthService,
        page_size: int = DEFAULT_PAGE_SIZE,
        sleep_between_pages: float = DEFAULT_SLEEP_BETWEEN_PAGES,
        page_timeout: int = DEFAULT_PAGE_TIMEOUT,
    ):
        self.auth = auth
        self.page_size = page_size
        self.sleep_between_pages = sleep_between_pages
        self.page_timeout = page_timeout
        self.fans = FansDataFetcher(auth, page_timeout=page_timeout)
        self.articles = ArticleStatsFetcher(auth, page_timeout=page_timeout)
        self.drafts = DraftsManager(auth, page_timeout=page_timeout)

    # ==================== 发表记录抓取 ====================
    def fetch_publishes(
        self,
        max_pages: int | None = None,
        max_retries: int = 2,
    ) -> list[dict]:
        """
        抓取全部发表记录。

        Args:
            max_pages: 最大翻页次数，None 表示不限
            max_retries: 遇到 cookie 失效时最大重试次数
        """
        token = self.auth.ensure_token()
        page = self.auth.page

        all_items: list[dict] = []
        begin = 0
        empty_times = 0
        total_count: int | None = None
        pages_fetched = 0

        while True:
            if max_pages is not None and pages_fetched >= max_pages:
                print(f"[spider] 已达到最大页数限制 {max_pages}")
                break

            try:
                publish_page, items = self._fetch_publish_page(page, token, begin)
            except CookieExpiredError:
                if max_retries <= 0:
                    raise
                print("[spider] 检测到登录态失效，尝试重新登录...")
                token = self.auth.refresh_login()
                max_retries -= 1
                continue
            except PlaywrightTimeout:
                print(f"[spider] 第 {begin} 页加载超时，结束抓取")
                break

            if total_count is None:
                total_count = publish_page.get("total_count") if isinstance(publish_page, dict) else None
                print(f"[spider] 发表记录总数: {total_count}")

            if not items:
                empty_times += 1
                if empty_times >= 2:
                    print("[spider] 连续两页无数据，结束翻页")
                    break
            else:
                empty_times = 0
                all_items.extend(items)
                print(f"[spider] 本页获取 {len(items)} 条，累计 {len(all_items)} 条")

            if len(items) < self.page_size:
                print("[spider] 本页数据不足 page_size，结束翻页")
                break

            if total_count is not None and len(all_items) >= total_count:
                print("[spider] 已获取全部记录")
                break

            begin += self.page_size
            pages_fetched += 1
            time.sleep(self.sleep_between_pages)

        return all_items

    def _fetch_publish_page(
        self,
        page,
        token: str,
        begin: int,
    ) -> tuple[dict, list[dict]]:
        """抓取某一页发表记录。"""
        url = (
            "https://mp.weixin.qq.com/cgi-bin/appmsgpublish"
            f"?t=media/appmsg_publish_v2&begin={begin}&count={self.page_size}"
            f"&token={token}&lang=zh_CN"
        )
        print(f"[spider] fetch publish page: begin={begin}, count={self.page_size}")

        page.goto(url, wait_until="networkidle", timeout=self.page_timeout)
        page_html = page.content()

        try:
            publish_page = PublishPageParser.parse(page_html)
        except FetchError as e:
            error_msg = str(e)
            if "登录页" in error_msg:
                raise CookieExpiredError(error_msg) from e
            raise

        items = PublishPageParser.extract_items(publish_page)
        return publish_page, items

    # ==================== 粉丝数据抓取 ====================
    def fetch_fans_summary(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        debug_dir: Path | None = None,
    ) -> dict:
        """抓取用户分析汇总数据。"""
        return self.fans.fetch_user_summary(start_date, end_date, debug_dir=debug_dir)

    def fetch_total_fans(self) -> int:
        """抓取当前总粉丝数。"""
        return self.fans.fetch_total_user_count()

    # ==================== 单篇文章阅读数据抓取 ====================
    def fetch_article_stats(
        self,
        appmsgid: int | str,
        itemidx: int = 1,
    ) -> dict:
        """根据 appmsgid 抓取单篇文章的编辑页数据。"""
        return self.articles.fetch_article_stats_by_appmsgid(appmsgid, itemidx)

    def fetch_public_article_stats(self, content_url: str) -> dict:
        """通过文章正文链接抓取公开阅读数据。"""
        return self.articles.fetch_article_stats_from_content_url(content_url)

    def fetch_article_content(
        self,
        content_url: str,
        include_html: bool = False,
    ) -> dict:
        """按需抓取单篇文章正文内容。"""
        return self.articles.fetch_article_content_from_content_url(content_url, include_html=include_html)

    def batch_fetch_articles_stats(
        self,
        publish_items: list[dict],
        include_public: bool = False,
    ) -> list[dict]:
        """基于发表记录批量抓取每篇文章的阅读数据。"""
        return self.articles.fetch_all_articles_stats(publish_items, include_public)

    # ==================== 导出工具 ====================
    @staticmethod
    def save(items: list[dict], output_dir: Path, prefix: str = "wechat_publishes") -> tuple[Path, Path]:
        """保存抓取结果为 JSON 和 CSV。"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        json_path = output_dir / f"{prefix}_{timestamp}.json"
        csv_path = output_dir / f"{prefix}_{timestamp}.csv"

        save_json(items, json_path)
        save_csv(items, csv_path)
        print(f"[spider] JSON 已保存: {json_path}")
        print(f"[spider] CSV 已保存: {csv_path}")
        return json_path, csv_path
