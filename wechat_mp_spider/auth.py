"""
微信公众号后台认证服务。

职责：
- 启动浏览器，让用户扫码登录
- 加载/保存 cookies
- 维护登录态，token 失效时自动重新登录
"""

import json
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from wechat_mp_spider.browser import BrowserManager
from wechat_mp_spider.config import COOKIE_FILE, DEFAULT_HEADLESS, DEFAULT_LOGIN_TIMEOUT, HOME_URL_PATTERN, LOGIN_URL
from wechat_mp_spider.exceptions import CookieExpiredError, LoginTimeoutError, TokenError
from wechat_mp_spider.utils import extract_token_from_url


class WechatAuthService:
    """微信后台认证服务。"""

    def __init__(
        self,
        cookie_file: Path = COOKIE_FILE,
        login_timeout: int = DEFAULT_LOGIN_TIMEOUT,
        headless: bool = DEFAULT_HEADLESS,
    ):
        self.cookie_file = Path(cookie_file)
        self.login_timeout = login_timeout
        self.headless = headless
        self._browser_manager: BrowserManager | None = None
        self._context = None
        self._page = None
        self._token: str | None = None

    # ==================== 上下文管理 ====================
    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        """启动浏览器并建立上下文。"""
        self._browser_manager = BrowserManager(headless=self.headless)
        self._browser_manager.start()
        self._context = self._browser_manager.context

    def stop(self):
        """关闭浏览器。"""
        if self._browser_manager:
            self._browser_manager.stop()
        self._browser_manager = None
        self._context = None
        self._page = None

    # ==================== Cookie 持久化 ====================
    def load_cookies(self) -> bool:
        """加载已保存的 cookies。"""
        if not self.cookie_file.exists():
            return False
        cookies = json.loads(self.cookie_file.read_text(encoding="utf-8"))
        self._context.add_cookies(cookies)
        print(f"[auth] 已加载历史 cookies: {self.cookie_file}")
        return True

    def save_cookies(self) -> None:
        """保存当前 cookies。"""
        cookies = self._context.cookies()
        self.cookie_file.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[auth] cookies 已保存: {self.cookie_file}")

    def clear_cookies(self) -> None:
        """删除本地 cookies 文件。"""
        if self.cookie_file.exists():
            self.cookie_file.unlink()
            print("[auth] 已清除本地 cookies")

    # ==================== 登录流程 ====================
    def login(self) -> str:
        """
        执行登录流程，返回有效的 token。
        如果有历史 cookies 会先尝试复用，失败则重新扫码。
        """
        if self._context is None:
            raise RuntimeError("请先调用 start() 启动浏览器")

        self._page = self._context.new_page()

        # 先尝试加载历史 cookies
        has_cookie = self.load_cookies()

        if has_cookie:
            try:
                token = self._try_reuse_login()
                if token:
                    self._token = token
                    return token
            except CookieExpiredError:
                print("[auth] 历史 cookies 已过期，准备重新扫码登录")
                self.clear_cookies()
                # 关闭旧页面，重新创建上下文页面
                self._page.close()
                self._page = self._context.new_page()

        if self.headless:
            raise LoginTimeoutError(
                "headless 模式无法完成首次扫码登录；"
                "请先设置 WECHAT_MP_HEADLESS=0 运行一次并扫码保存 cookies，"
                "之后即可使用 headless 复用登录态爬取。"
            )

        return self._scan_login()

    def _try_reuse_login(self) -> str | None:
        """尝试用已有 cookies 直接访问后台首页，看 token 是否有效。"""
        print("[auth] 尝试复用登录态...")
        self._page.goto(LOGIN_URL, wait_until="domcontentloaded")

        # 微信如果 cookie 有效，访问登录页会自动跳转到 home
        try:
            self._page.wait_for_url(HOME_URL_PATTERN, timeout=10_000)
        except PlaywrightTimeout:
            return None

        token = extract_token_from_url(self._page.url)
        if token:
            print(f"[auth] 登录态复用成功，token={token}")
            self.save_cookies()
            return token
        return None

    def _scan_login(self) -> str:
        """调起扫码登录。"""
        print("[auth] 打开微信公众号登录页...")
        self._page.goto(LOGIN_URL, wait_until="domcontentloaded")

        print("[auth] 请使用微信扫码登录...")
        try:
            self._page.wait_for_url(HOME_URL_PATTERN, timeout=self.login_timeout)
        except PlaywrightTimeout:
            raise LoginTimeoutError(f"{self.login_timeout // 1000} 秒内未检测到登录成功")

        token = extract_token_from_url(self._page.url)
        if not token:
            raise TokenError("无法从登录后 URL 提取 token")

        print(f"[auth] 登录成功，token={token}")
        self.save_cookies()
        self._token = token
        return token

    # ==================== Token 失效自动重登 ====================
    def ensure_token(self) -> str:
        """
        获取当前有效 token。
        如果 token 不存在，会触发登录流程。
        """
        if self._token:
            return self._token
        return self.login()

    def refresh_login(self) -> str:
        """强制重新登录（例如爬虫检测到 cookie 失效时调用）。"""
        self.clear_cookies()
        if self._page:
            self._page.close()
        if self.headless:
            raise LoginTimeoutError(
                "登录态已失效，headless 模式无法重新扫码；"
                "请设置 WECHAT_MP_HEADLESS=0 重新登录并保存 cookies 后再运行。"
            )
        self._page = self._context.new_page()
        return self._scan_login()

    @property
    def token(self) -> str | None:
        return self._token

    @property
    def page(self):
        if self._page is None:
            raise RuntimeError("尚未登录，请先调用 login()")
        return self._page
