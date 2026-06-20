"""全局配置。"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
COOKIE_FILE = BASE_DIR / "wechat_mp_cookies.json"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

LOGIN_URL = "https://mp.weixin.qq.com/"
HOME_URL_PATTERN = "**/cgi-bin/home**"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# 默认请求参数
DEFAULT_PAGE_SIZE = 10
DEFAULT_SLEEP_BETWEEN_PAGES = 2.0
DEFAULT_PAGE_TIMEOUT = 30_000
DEFAULT_LOGIN_TIMEOUT = 120_000
DEFAULT_HEADLESS = os.getenv("WECHAT_MP_HEADLESS", "1").lower() not in {"0", "false", "no", "off"}
