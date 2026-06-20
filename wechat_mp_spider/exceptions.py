"""自定义异常。"""


class WechatSpiderError(Exception):
    """基础异常。"""


class AuthError(WechatSpiderError):
    """登录认证相关异常。"""


class TokenError(AuthError):
    """无法提取 token。"""


class LoginTimeoutError(AuthError):
    """扫码登录超时。"""


class FetchError(WechatSpiderError):
    """数据抓取异常。"""


class CookieExpiredError(AuthError):
    """Cookie 失效。"""
