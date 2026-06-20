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


# 保存草稿所需的默认表单字段模板
# 基于微信后台真实请求构建，覆盖文章设置、评论、封面、广告等字段
_DRAFT_FIELD_DEFAULTS = {
    # 基础
    "count": 1,
    "data_seq": 0,
    "operate_from": "Chrome",
    "isnew": 0,
    "autosave_log": "true",
    "articlenum": 1,
    "pre_timesend_set": 0,
    "is_auto_type_setting": 3,
    "save_type": 1,
    "isneedsave": 0,
    # 文章索引 0 的默认值
    "is_finder_video0": 0,
    "finder_draft_id0": 0,
    "applyori0": 0,
    "ad_video_transition0": "",
    "can_reward0": 0,
    "pay_gifts_count0": 0,
    "reward_reply_id0": "",
    "related_video0": "",
    "is_video_recommend0": -1,
    "is_user_title0": "",
    "writerid0": 0,
    "fileid0": "",
    "auto_gen_digest0": 0,
    "sourceurl0": "",
    "last_choose_cover_from0": 0,
    "need_open_comment0": 1,
    "only_fans_can_comment0": 0,
    "only_fans_days_can_comment0": 0,
    "reply_flag0": 2,
    "not_pay_can_comment0": 0,
    "auto_elect_comment0": 1,
    "auto_elect_reply0": 1,
    "option_version0": 5,
    "open_fansmsg0": 0,
    "cdn_url0": "",
    "cdn_235_1_url0": "",
    "cdn_16_9_url0": "",
    "cdn_3_4_url0": "",
    "cdn_1_1_url0": "",
    "cdn_finder_url0": "",
    "cdn_video_url0": "",
    "cdn_url_back0": "",
    "crop_list0": "",
    "app_cover_auto0": 0,
    "music_id0": "",
    "video_id0": "",
    "voteid0": "",
    "voteismlt0": "",
    "supervoteid0": "",
    "super_vote_id0": "",
    "vid_type0": "",
    "show_cover_pic0": 0,
    "copyright_type0": 0,
    "is_cartoon_copyright0": 0,
    "copyright_img_list0": '{"max_width":586,"img_list":[]}',
    "releasefirst0": "",
    "platform0": "",
    "reprint_permit_type0": "",
    "allow_fast_reprint0": 0,
    "allow_reprint0": "",
    "allow_reprint_modify0": "",
    "original_article_type0": "",
    "ori_white_list0": "",
    "video_ori_status0": "",
    "hit_nickname0": "",
    "free_content0": "",
    "fee0": 0,
    "ad_id0": "",
    "guide_words0": "",
    "is_share_copyright0": 0,
    "share_copyright_url0": "",
    "source_article_type0": "",
    "reprint_recommend_title0": "",
    "reprint_recommend_content0": "",
    "share_page_type0": 0,
    "share_imageinfo0": '{"list":[]}',
    "share_video_id0": "",
    "dot0": "{}",
    "share_voice_id0": "",
    "share_finder_audio_username0": "",
    "share_finder_audio_exportid0": "",
    "mmlistenitem_json_buf0": "",
    "insert_ad_mode0": 0,
    "categories_list0": "[]",
    "is_pay_subscribe0": 0,
    "pay_fee0": "",
    "pay_preview_percent0": "",
    "pay_desc0": "",
    "pay_album_info0": "",
    "appmsg_album_info0": '{"appmsg_album_infos":[]}',
    "can_insert_ad0": 1,
    "open_keyword_ad0": 0,
    "open_comment_ad0": 1,
    "audio_info0": '{"audio_infos":[]}',
    "danmu_pub_type0": 0,
    "mp_video_info0": '{"list":[]}',
    "appmsg_danmu_pub_type0": "",
    "is_set_sync_to_finder0": 0,
    "sync_to_finder_cover0": "",
    "sync_to_finder_cover_source0": "",
    "import_to_finder0": 0,
    "import_from_finder_export_id0": "",
    "style_type0": 3,
    "sticker_info0": '{"is_stickers":0,"common_stickers_num":0,"union_stickers_num":0,"sticker_id_list":[],"has_invalid_sticker":0}',
    "new_pic_process0": 0,
    "disable_recommend0": 0,
    "claim_source_type0": "",
    "is_user_no_claim_source0": 0,
    "msg_index_id0": "",
    "convert_to_image_share_page0": "",
    "convert_from_image_share_page0": "",
    "incontent_ad_count0": 0,
    "multi_picture_cover0": 0,
    "title_gen_type0": 0,
    "req": '{"idx_infos":[{"save_old":0,"cps_info":{"cps_import":0},"red_packet_cover_list":{},"podcast_task_info":null,"claim_source":{},"line_info":{"is_appmsg_flag":0,"scene":2},"window_product":{},"link_info":{},"appmsg_link":{},"weapp_link":{},"yqj_info":{},"ai_pic_info":{"ai_pic_id":[]},"single_video_snap_card":{},"product_activity":{},"footer_gift_activity":{},"footer_common_shops":[],"location":{}}],"appmsg_id":0,"is_use_flag":0,"template_version":"55321812"}',
}


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
    def _build_save_fields(
        self,
        title: str,
        content: str,
        author: str = "",
        digest: str = "",
        cover_url: str = "",
        content_source_url: str = "",
        need_open_comment: int = 0,
        only_fans_can_comment: int = 0,
        appmsgid: int | str | None = None,
    ) -> dict:
        """构造保存草稿所需的完整 form-data 字段。"""
        token = self.auth.ensure_token()
        now_ts = str(int(time.time()))

        fields = {
            **_DRAFT_FIELD_DEFAULTS,
            "token": token,
            "lang": "zh_CN",
            "f": "json",
            "ajax": 1,
            "fingerprint": "",
            "random": now_ts,
            "AppMsgId": str(appmsgid) if appmsgid is not None else "",
            "appmsgid": str(appmsgid) if appmsgid is not None else "",
            "title0": title,
            "author0": author,
            "digest0": digest,
            "content0": content,
            "sourceurl0": content_source_url,
            "cdn_url0": cover_url,
            "need_open_comment0": need_open_comment,
            "only_fans_can_comment0": int(only_fans_can_comment),
            "auto_gen_digest0": 0 if digest else 1,
        }

        if appmsgid is not None:
            req = json.loads(fields["req"])
            req["appmsg_id"] = int(appmsgid)
            fields["req"] = json.dumps(req, ensure_ascii=False, separators=(",", ":"))

        return fields

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
        token = self.auth.ensure_token()
        url = f"https://mp.weixin.qq.com/cgi-bin/operate_appmsg?t=ajax-response&sub=create&type=77&token={token}&lang=zh_CN"

        fields = self._build_save_fields(
            title=title,
            content=content,
            author=author,
            digest=digest,
            cover_url=cover_url,
            content_source_url=content_source_url,
            need_open_comment=need_open_comment,
            only_fans_can_comment=only_fans_can_comment,
        )

        response = session.post(
            url,
            data=fields,
            headers=self._headers(referer_path="appmsg"),
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
        token = self.auth.ensure_token()
        url = f"https://mp.weixin.qq.com/cgi-bin/operate_appmsg?t=ajax-response&sub=create&type=77&token={token}&lang=zh_CN"

        fields = self._build_save_fields(
            title=title,
            content=content,
            author=author,
            digest=digest,
            cover_url=cover_url,
            content_source_url=content_source_url,
            need_open_comment=need_open_comment,
            only_fans_can_comment=only_fans_can_comment,
            appmsgid=appmsgid,
        )

        response = session.post(
            url,
            data=fields,
            headers=self._headers(referer_path="appmsg"),
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
