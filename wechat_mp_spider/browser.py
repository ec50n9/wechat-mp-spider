"""Playwright 浏览器生命周期管理。"""

from playwright.sync_api import sync_playwright

from wechat_mp_spider.config import USER_AGENT


class BrowserManager:
    """管理 Playwright 浏览器实例和上下文。"""

    def __init__(self, headless: bool = False):
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._context = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        """启动浏览器。"""
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
            ],
        )
        self._context = self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=USER_AGENT,
        )

    def stop(self):
        """关闭浏览器。"""
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
        self._context = None

    @property
    def context(self):
        if self._context is None:
            raise RuntimeError("浏览器未启动")
        return self._context

    def new_page(self):
        return self.context.new_page()
