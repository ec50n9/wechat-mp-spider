# 微信公众号数据采集工具

自动抓取你的公众号后台数据：发表记录、粉丝趋势、文章阅读/点赞/分享，还能一键生成内容优化报告。

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## 30 秒上手

### 1. 安装

```bash
git clone https://github.com/ec50n9/wechat-mp-spider.git
cd wechat-mp-spider

pip install -r requirements.txt
python -m playwright install chromium
```

### 2. 首次扫码登录

```bash
# 弹出浏览器窗口扫码，登录态会自动保存
WECHAT_MP_HEADLESS=0 python main.py publishes
```

扫码成功后，`wechat_mp_cookies.json` 会保存你的登录态，后续命令默认在后台运行。

### 3. 日常采集

```bash
# 抓取全部发表记录
python main.py publishes

# 抓取粉丝数据
python main.py fans --start-date 2024-01-01 --end-date 2024-01-31

# 基于发表记录抓取文章阅读、点赞、分享数据
python main.py article-stats --publishes-file output/xxx/wechat_publishes_xxx.json

# 或者直接临时抓取发表记录再统计文章
python main.py article-stats --fetch-publishes

# 抓取单篇文章正文
python main.py article-content --url 'https://mp.weixin.qq.com/s/xxxxxx'

# 生成数据分析报告
python main.py report \
  --article-stats-file output/xxx/wechat_article_stats_xxx.json \
  --fans-summary-file output/xxx/wechat_fans_summary_normalized.json
```

每次运行都会在 `output/` 下生成一个带时间戳的目录，数据自动归档。

---

## 实际效果

### 抓取发表记录

```bash
python main.py publishes --max-pages 3
```

输出示例：

```
===== 抓取发表记录 =====
[done] 共抓取 30 条发表记录
{
  "title": "为什么你的 Python 脚本越写越慢",
  "publish_time": "2024-01-15 09:30:00",
  "content_url": "https://mp.weixin.qq.com/s/xxxxx",
  ...
}
```

### 抓取文章统计数据

```bash
python main.py article-stats --fetch-publishes --include-public
```

输出包含每篇文章的阅读数、点赞数、在看数、分享数、收藏数，以及标题、摘要、封面等元数据。

### 生成分析报告

```bash
python main.py report \
  --article-stats-file output/20240620_210512/wechat_article_stats_xxx.json \
  --fans-summary-file output/20240620_210512/wechat_fans_summary_normalized.json
```

会自动生成 `analysis.md`，包含：

- 阅读 Top 10 / 互动 Top 10
- 标题长度、发布时间、文章位置对阅读量的影响
- 粉丝增长趋势
- 下次写什么、怎么优化的具体建议

---

## 命令速查

```bash
python main.py --help
```

| 命令 | 作用 | 示例 |
|------|------|------|
| `publishes` | 抓取发表记录 | `python main.py publishes --max-pages 5` |
| `fans` | 抓取粉丝汇总 | `python main.py fans --start-date 2024-01-01` |
| `article-stats` | 文章阅读/互动数据 | `python main.py article-stats --fetch-publishes` |
| `article-content` | 单篇文章正文 | `python main.py article-content --url <URL>` |
| `report` | 生成分析报告 | `python main.py report --article-stats-file <文件>` |

通用选项：

- `--output-dir`：输出目录，默认 `output/`
- `--headless / --no-headless`：是否后台运行浏览器
- `--help`：查看命令帮助

---

## 一个完整的工作流

```bash
# 1. 抓取发表记录
python main.py publishes

# 假设输出目录为 output/20240620_210512
# 2. 基于发表记录抓取文章统计
python main.py article-stats \
  --publishes-file output/20240620_210512/wechat_publishes_xxx.json

# 3. 抓取粉丝数据
python main.py fans

# 4. 生成分析报告
python main.py report \
  --article-stats-file output/20240620_210512/wechat_article_stats_xxx.json \
  --fans-summary-file output/20240620_210512/wechat_fans_summary_normalized.json
```

然后打开 `output/20240620_210512/analysis.md` 即可看到分析结论。

---

## 常见问题

**Q: 登录态会过期吗？**  
A: 会。过期后再次运行任意命令会自动重新扫码，或手动用 `WECHAT_MP_HEADLESS=0 python main.py publishes` 重新登录。

**Q: 可以不开浏览器窗口吗？**  
A: 可以。首次扫码后，后续默认 headless 模式在后台运行。

**Q: 输出文件在哪里？**  
A: 每次运行都会在 `output/` 下生成 `YYYYMMDD_HHMMSS` 目录，所有结果按时间归档。

**Q: 会不会提交我的 cookies 到 GitHub？**  
A: 不会。`wechat_mp_cookies.json`、`output/`、`.env` 等敏感/临时文件已在 `.gitignore` 中排除。

---

## 声明

本工具仅用于采集你自己拥有管理权限的微信公众号数据，请遵守微信平台规则，合理控制请求频率。
