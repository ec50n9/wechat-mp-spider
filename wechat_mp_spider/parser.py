"""微信后台页面/响应解析器。"""

import json
import re

from wechat_mp_spider.exceptions import FetchError
from wechat_mp_spider.utils import unescape_json_string


class PublishPageParser:
    """解析发表记录 SSR 页面中的 publish_page 数据。"""

    # 发表记录页面内嵌变量的可能名称
    _VAR_CANDIDATES = ("publish_page_noencode", "publish_page")

    @classmethod
    def parse(cls, page_html: str) -> dict:
        """从页面 HTML 中解析 publish_page 对象。"""
        page_html = page_html.strip()

        # 直接 JSON（偶尔接口会返回纯 JSON）
        if page_html.startswith("{") or page_html.startswith("["):
            try:
                return json.loads(page_html)
            except json.JSONDecodeError:
                pass

        # 优先匹配无编码变量
        for var_name in cls._VAR_CANDIDATES:
            pattern = rf"let\s+{var_name}\s*=\s*(\{{[\s\S]*?\}});"
            match = re.search(pattern, page_html)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue

        # 兜底匹配
        match = re.search(r"publish_page\s*=\s*(\{[\s\S]*?\});", page_html)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError as e:
                raise FetchError(f"publish_page JSON 解析失败: {e}")

        # 检测是否被踢到登录页
        if "登录" in page_html and "publish_page" not in page_html:
            raise FetchError("页面被重定向到登录页，需要重新登录")

        raise FetchError("无法从页面中解析 publish_page")

    @classmethod
    def extract_items(cls, publish_page: dict) -> list[dict]:
        """
        从 publish_page 中提取发表记录列表。
        会把 publish_info 中的 HTML 转义 JSON 字符串解析为对象。
        """
        raw_items = publish_page.get("publish_list", []) if isinstance(publish_page, dict) else []
        items = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            new_item = dict(item)
            pi = new_item.get("publish_info")
            if isinstance(pi, str):
                try:
                    new_item["publish_info"] = unescape_json_string(pi)
                except json.JSONDecodeError as e:
                    raise FetchError(f"publish_info 解析失败: {e}")
            items.append(new_item)
        return items


class BaseParser:
    """后续其他数据类型的解析器可以继承或参考这里。"""

    @classmethod
    def parse(cls, page_html: str) -> dict:
        raise NotImplementedError
