"""
公众号粉丝/用户数据抓取。

数据来源：公众号后台「统计」->「用户分析」页面。
该页面数据通过 window.CGI_DATA 内嵌，结构如下：
window.CGI_DATA['pages/statistics/user_statistics'] = {
    list: [
        {
            user_source: 99999999,
            list: [
                { date: "2026-05-20", cancel_user: 0, cumulate_user: 129, netgain_user: 0, new_user: 0 },
                ...
            ]
        },
        ...
    ]
}
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from wechat_mp_spider.config import DEFAULT_PAGE_TIMEOUT
from wechat_mp_spider.exceptions import FetchError
from wechat_mp_spider.js_engine import js_object_to_json


class FansDataFetcher:
    """粉丝/用户数据获取器。"""

    def __init__(self, auth, page_timeout: int = DEFAULT_PAGE_TIMEOUT):
        self.auth = auth
        self.page_timeout = page_timeout

    def _fans_url(self, path: str, token: str) -> str:
        """构建后台粉丝/用户相关 URL。"""
        return f"https://mp.weixin.qq.com{path}&token={token}&lang=zh_CN"

    def fetch_user_summary(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        max_wait_ms: int = 10_000,
        debug_dir: Path | None = None,
    ) -> dict:
        """
        抓取用户分析汇总数据。

        Args:
            start_date: 开始日期，格式 YYYY-MM-DD，默认 7 天前
            end_date: 结束日期，格式 YYYY-MM-DD，默认今天
            max_wait_ms: 等待页面数据加载的最大时间
            debug_dir: 调试页面输出目录，None 表示不保存调试页面

        Returns:
            {
                "dates": ["2026-06-13", ...],
                "new_user": [1, 2, ...],
                "cancel_user": [0, 1, ...],
                "net_gain": [1, 1, ...],
                "cumulate_user": [128, 129, ...],
            }
        """
        token = self.auth.ensure_token()
        page = self.auth.page

        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        path = "/misc/useranalysis?"
        url = self._fans_url(path, token)
        print(f"[fans] 访问用户分析页面: {url}")

        page.goto(url, wait_until="networkidle", timeout=self.page_timeout)
        page.wait_for_timeout(max_wait_ms)

        html = page.content()

        if debug_dir:
            debug_dir.mkdir(parents=True, exist_ok=True)
            debug_path = debug_dir / f"fans_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            debug_path.write_text(html, encoding="utf-8")
            print(f"[fans] 已保存调试页面: {debug_path}")

        raw_data = self._extract_cgi_data(html)
        if raw_data:
            items = self._extract_summary_items(raw_data)
            if items:
                return self._normalize_user_summary(items, start_date, end_date)

        # 兜底：如果 CGI_DATA 是 JS 对象字面量，尝试用 JS 引擎解析
        cgi_match = __import__("re").search(
            r"window\.CGI_DATA\['pages/statistics/user_statistics'\]\s*=\s*(\{[\s\S]*?\});",
            html,
        )
        if cgi_match:
            try:
                raw_data = js_object_to_json(cgi_match.group(1))
                items = self._extract_summary_items(raw_data)
                if items:
                    return self._normalize_user_summary(items, start_date, end_date)
            except Exception as e:
                print(f"[warn] JS 引擎解析失败: {e}")

        raise FetchError("无法从用户分析页面提取粉丝数据")

    def _extract_cgi_data(self, html: str) -> dict | None:
        """解析 window.CGI_DATA['pages/statistics/user_statistics']。"""
        pattern = r"window\.CGI_DATA\['pages/statistics/user_statistics'\]\s*=\s*(\{[\s\S]*?\});"
        match = re.search(pattern, html)
        if match:
            try:
                # 先尝试标准 JSON
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                # 再尝试 JS 对象字面量
                try:
                    return js_object_to_json(match.group(1))
                except Exception as e:
                    print(f"[warn] CGI_DATA 解析失败: {e}")
        return None

    def _extract_summary_items(self, raw_data: dict) -> list[dict]:
        """
        从 CGI_DATA 中找到 user_source=99999999 的汇总列表。
        """
        if not isinstance(raw_data, dict):
            return []
        for group in raw_data.get("list", []):
            if isinstance(group, dict) and group.get("user_source") == 99999999:
                return group.get("list", [])
        # 兜底：返回第一个 list
        for group in raw_data.get("list", []):
            if isinstance(group, dict) and "list" in group:
                return group["list"]
        return []

    def _normalize_user_summary(self, items: list[dict], start_date: str, end_date: str) -> dict:
        """把原始数据归一化。"""
        return {
            "start_date": start_date,
            "end_date": end_date,
            "dates": [item.get("date") for item in items],
            "new_user": [item.get("new_user", 0) for item in items],
            "cancel_user": [item.get("cancel_user", 0) for item in items],
            "net_gain": [item.get("netgain_user", 0) for item in items],
            "cumulate_user": [item.get("cumulate_user", 0) for item in items],
            "raw": items,
        }

    def fetch_total_user_count(self) -> int:
        """
        抓取当前总粉丝数。
        通过访问用户分析页面，读取汇总数据最后一天（今天）的 cumulate_user。
        """
        summary = self.fetch_user_summary()
        cumulate = summary.get("cumulate_user", [])
        if cumulate:
            return int(cumulate[-1])
        raise FetchError("无法从用户分析汇总提取总粉丝数")
