"""
微信公众号草稿箱操作。

职责：
- 获取草稿箱列表
- 获取单篇草稿详情
- 创建/保存草稿
- 删除草稿

实现方式基于微信公众平台后台的 cgi-bin 接口。
"""

import json
import time
from pathlib import Path

import requests

from wechat_mp_spider.auth import WechatAuthService
from wechat_mp_spider.config import DEFAULT_PAGE_TIMEOUT
from wechat_mp_spider.exceptions import FetchError
from wechat_mp_spider.utils import extract_token_from_url


class DraftsManager:
    """微信公众号草稿箱管理。"""

    def __init__(
        self,
        auth: WechatAuthService,
        page_timeout: int = DEFAULT_PAGE_TIMEOUT,
    ):
        self.auth = auth
        self.page_timeout = page_timeout
        self._session: requests.Session | None = None

    # ==================== 请求构造 ====================
    def _ensure_session(self) -> requests.Session:
        """初始化并返回一个已携带 cookies 的 requests 会话。"""
        if self._session is not None:
            return self._session

        token = self.auth.ensure_token()
        page = self.auth.page
        cookies = page.context.cookies()

        session = requests.Session()
        for cookie in cookies:
            session.cookies.set(
                name=cookie["name"],
                value=cookie["value"],
                domain=cookie.get("domain", ""),
                path=cookie.get("path", "/"),
            )
        self._session = session
        return session

    def _base_url(self, path: str) -> str:
        """构造带 token 的接口 URL。"""
        token = self.auth.ensure_token()
        return f"https://mp.weixin.qq.com/cgi-bin/{path}?token={token}&lang=zh_CN"

    def _headers(self, referer_path: str = "appmsg") -> dict:
        """构造常用请求头。"""
        return {
            "Referer": f"https://mp.weixin.qq.com/cgi-bin/{referer_path}?t=media/appmsg_list_v2",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }

    # ==================== 草稿列表 ====================
    def fetch_drafts(
        self,
        count: int = 10,
        offset: int = 0,
        query: str = "",
    ) -> dict:
        """
        获取草稿箱列表。

        Args:
            count: 每页数量
            offset: 起始偏移
            query: 搜索关键词
        """
        session = self._ensure_session()
        url = self._base_url("appmsg")

        params = {
            "t": "media/appmsg_list_v2",
            "action": "list_ex",
            "begin": offset,
            "count": count,
            "type": 10,  # 图文消息
            "query": query,
            "f": "json",
        }

        response = session.get(url, params=params, headers=self._headers(), timeout=self.page_timeout / 1000)
        response.raise_for_status()
        data = response.json()

        if data.get("base_resp", {}).get("ret") not in (0, None):
            raise FetchError(f"获取草稿列表失败: {data}")

        return data

    def fetch_all_drafts(
        self,
        max_pages: int | None = None,
        page_size: int = 10,
        query: str = "",
    ) -> list[dict]:
        """翻页获取全部草稿。"""
        all_items: list[dict] = []
        offset = 0
        pages = 0

        while True:
            if max_pages is not None and pages >= max_pages:
                break

            result = self.fetch_drafts(count=page_size, offset=offset, query=query)
            items = result.get("app_msg_list", [])
            if not items:
                break

            all_items.extend(items)
            offset += len(items)
            pages += 1
            time.sleep(0.5)

        return all_items

    # ==================== 草稿详情 ====================
    def fetch_draft_detail(self, appmsgid: int | str) -> dict:
        """获取单篇草稿详情。"""
        session = self._ensure_session()
        url = self._base_url("appmsg")

        params = {
            "t": "media/appmsg_edit_v2",
            "action": "edit",
            "appmsgid": appmsgid,
            "type": 10,
            "isMul": 1,
            "f": "json",
        }

        response = session.get(url, params=params, headers=self._headers(), timeout=self.page_timeout / 1000)
        response.raise_for_status()
        data = response.json()

        if data.get("base_resp", {}).get("ret") not in (0, None):
            raise FetchError(f"获取草稿详情失败: {data}")

        return data

    # ==================== 创建/更新草稿 ====================
    def create_draft(
        self,
        title: str,
        content: str,
        author: str = "",
        digest: str = "",
        cover_url: str = "",
        content_source_url: str = "",
        need_open_comment: int = 0,
        only_fans_can_comment: int = 0,
    ) -> dict:
        """
        创建一篇图文草稿。

        Args:
            title: 标题
            content: 正文内容，支持 HTML
            author: 作者
            digest: 摘要
            cover_url: 封面图片 URL
            content_source_url: 原文链接
            need_open_comment: 是否打开评论，1 开启，0 关闭
            only_fans_can_comment: 是否仅粉丝可评论，1 是，0 否
        """
        session = self._ensure_session()
        url = self._base_url("operate_appmsg")

        post_data = {
            "token": self.auth.ensure_token(),
            "lang": "zh_CN",
            "f": "json",
            "ajax": 1,
            "AppMsgId": "",
            "compose_info": json.dumps({
                "list": [
                    {
                        "appmsg_info": {
                            "title": title,
                            "content": content,
                            "author": author,
                            "digest": digest,
                            "cover": cover_url,
                            "content_source_url": content_source_url,
                            "need_open_comment": need_open_comment,
                            "only_fans_can_comment": only_fans_can_comment,
                        },
                        "file_info": {"type": 1},
                    }
                ]
            }),
        }

        response = session.post(
            url,
            data=post_data,
            headers=self._headers(referer_path="operate_appmsg"),
            timeout=self.page_timeout / 1000,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("base_resp", {}).get("ret") not in (0, None):
            raise FetchError(f"创建草稿失败: {data}")

        return data

    def update_draft(
        self,
        appmsgid: int | str,
        title: str,
        content: str,
        author: str = "",
        digest: str = "",
        cover_url: str = "",
        content_source_url: str = "",
        need_open_comment: int = 0,
        only_fans_can_comment: int = 0,
    ) -> dict:
        """更新一篇已有草稿。"""
        session = self._ensure_session()
        url = self._base_url("operate_appmsg")

        post_data = {
            "token": self.auth.ensure_token(),
            "lang": "zh_CN",
            "f": "json",
            "ajax": 1,
            "AppMsgId": appmsgid,
            "compose_info": json.dumps({
                "list": [
                    {
                        "appmsg_info": {
                            "appmsgid": appmsgid,
                            "title": title,
                            "content": content,
                            "author": author,
                            "digest": digest,
                            "cover": cover_url,
                            "content_source_url": content_source_url,
                            "need_open_comment": need_open_comment,
                            "only_fans_can_comment": only_fans_can_comment,
                        },
                        "file_info": {"type": 1},
                    }
                ]
            }),
        }

        response = session.post(
            url,
            data=post_data,
            headers=self._headers(referer_path="operate_appmsg"),
            timeout=self.page_timeout / 1000,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("base_resp", {}).get("ret") not in (0, None):
            raise FetchError(f"更新草稿失败: {data}")

        return data

    # ==================== 删除草稿 ====================
    def delete_draft(self, appmsgid: int | str) -> dict:
        """删除一篇草稿。"""
        session = self._ensure_session()
        url = self._base_url("operate_appmsg")

        post_data = {
            "token": self.auth.ensure_token(),
            "lang": "zh_CN",
            "f": "json",
            "ajax": 1,
            "sub": "del",
            "appmsgid": appmsgid,
            "type": 10,
        }

        response = session.post(
            url,
            data=post_data,
            headers=self._headers(referer_path="operate_appmsg"),
            timeout=self.page_timeout / 1000,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("base_resp", {}).get("ret") not in (0, None):
            raise FetchError(f"删除草稿失败: {data}")

        return data
