# 微信公众号后台数据服务化采集工具

## 项目位置

`~/projects/wechat-mp-spider`

## 项目结构

```
~/projects/wechat-mp-spider
├── main.py                        # 入口脚本：抓取发表记录、粉丝、文章数据
├── inspect_response.py            # 调试脚本
├── requirements.txt
├── README.md
├── wechat_mp_cookies.json         # 登录态 cookies（自动生成）
├── output/                        # 结果输出目录
└── wechat_mp_spider/              # 核心包
    ├── __init__.py
    ├── auth.py                    # 基础设施：浏览器、扫码、cookie、自动重登
    ├── browser.py                 # Playwright 浏览器生命周期管理
    ├── config.py                  # 全局配置
    ├── exceptions.py              # 自定义异常
    ├── fans.py                    # 公众号粉丝/用户数据抓取
    ├── article_stats.py           # 单篇文章阅读数据抓取
    ├── js_engine.py               # JS 对象字面量解析器
    ├── js_helpers.py              # 页面内执行的 JS 辅助函数
    ├── parser.py                  # 发表记录页面解析器
    ├── spider.py                  # 爬虫主入口，组合各数据抓取能力
    └── utils.py                   # 通用工具
```

## 设计思路

- **基础设施层** (`auth.py` / `browser.py`)：负责浏览器启动、扫码登录、cookie 持久化、登录态失效自动重登。
- **业务逻辑层** (`fans.py` / `article_stats.py` / `parser.py`)：负责具体数据的抓取和解析，容易扩展新的数据类型。
- **编排层** (`spider.py`)：组合各数据抓取能力，提供统一入口。
- **工具层** (`utils.py` / `config.py` / `exceptions.py` / `js_engine.py`)：通用导出、配置、异常和 JS 解析工具。

## 已支持的数据

| 数据类型 | 方法 | 说明 |
|---------|------|------|
| 发表记录 | `spider.fetch_publishes()` | 自动翻页抓取全部发表记录 |
| 总粉丝数 | `spider.fetch_total_fans()` | 当前公众号总粉丝数 |
| 用户分析汇总 | `spider.fetch_fans_summary()` | 每日新增/取关/净增/累计粉丝 |
| 单篇文章阅读数据 | `spider.batch_fetch_articles_stats()` | 基于发表记录批量提取阅读数、点赞数、标题、摘要、封面等 |
| 公开文章阅读数 | `spider.fetch_public_article_stats(url)` | 访问文章正文页抓取公开阅读数 |
| 按需文章正文 | `spider.fetch_article_content(url)` | 需要分析具体文章时再抓取正文文本/HTML |
| 自动分析报告 | `generate_analysis_report()` | 基于文章和粉丝数据生成内容优化建议 |

## 安装

```bash
cd ~/projects/wechat-mp-spider
pip install -r requirements.txt
python -m playwright install chromium
```

## 使用

### 一键抓取全部数据

```bash
python main.py
```

首次登录需要设置 `WECHAT_MP_HEADLESS=0` 弹出浏览器窗口扫码；登录态会保存到 `wechat_mp_cookies.json`，后续默认使用 headless 模式自动复用。每次运行会在 `output/` 下创建独立目录，保存发表记录、粉丝数据、文章数据和 `analysis.md` 分析报告。

```bash
# 首次登录/登录态失效时：有界面扫码并保存 cookies
WECHAT_MP_HEADLESS=0 python main.py

# 已有有效 cookies 后：默认 headless 爬取
python main.py
```

### 作为服务使用

```python
from wechat_mp_spider import WechatAuthService, WechatSpider
from wechat_mp_spider.config import OUTPUT_DIR

with WechatAuthService(headless=True) as auth:
    spider = WechatSpider(auth)

    # 发表记录
    publishes = spider.fetch_publishes()
    spider.save(publishes, OUTPUT_DIR, prefix="wechat_publishes")

    # 粉丝数据
    fans_summary = spider.fetch_fans_summary()
    total_fans = int(fans_summary["cumulate_user"][-1])

    # 文章阅读数据（包含标题、摘要、封面等元数据）
    article_stats = spider.batch_fetch_articles_stats(publishes)
    spider.save(article_stats, OUTPUT_DIR, prefix="wechat_article_stats")

    # 按需抓取具体文章正文
    content = spider.fetch_article_content(article_stats[0]["content_url"])
```

## 扩展新的数据类型

1. 在 `wechat_mp_spider/` 下新增数据获取器（例如 `message.py`）
2. 在 `spider.py` 的 `__init__` 中初始化并暴露方法
3. 在业务脚本或 `main.py` 中调用

## 配置项

在 `wechat_mp_spider/config.py` 中可调整：

- `DEFAULT_PAGE_SIZE`：每页条数
- `DEFAULT_SLEEP_BETWEEN_PAGES`：翻页间隔
- `DEFAULT_PAGE_TIMEOUT`：页面加载超时
- `DEFAULT_LOGIN_TIMEOUT`：扫码登录超时
- `DEFAULT_HEADLESS`：是否默认使用 headless 模式，可通过环境变量 `WECHAT_MP_HEADLESS=0/1` 覆盖

## 登录态失效处理

- `WechatAuthService` 启动时会尝试复用 `wechat_mp_cookies.json`
- 如果 cookies 过期，会自动清除并重新扫码登录
- 爬虫运行中检测到登录页重定向时，也会调用 `auth.refresh_login()` 重新登录

## 注意事项

- 本工具仅用于采集你自己运营的公众号数据
- 建议保持合理的请求频率，避免触发平台风控
- 粉丝数据页面使用 `window.CGI_DATA` 内嵌 JS 对象，已用 `js_engine.py` 做非标准 JSON 解析
