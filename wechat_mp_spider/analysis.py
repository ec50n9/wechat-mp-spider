"""公众号文章表现分析报告。"""

import re
from collections.abc import Iterable
from datetime import datetime
from statistics import median


TOPIC_PATTERNS = [
    ("AI/工具", re.compile(r"AI|Agent|Claude|Codex|Gemini|模型|工具|编程|编码|MCP|LLM|prompt|提示词", re.I)),
    ("产品/设计", re.compile(r"产品|设计|体验|需求|用户|交互|输入框|界面", re.I)),
    ("效率/工作流", re.compile(r"效率|工作流|自动化|流程|协作|复盘|缓冲层", re.I)),
    ("教程/实践", re.compile(r"怎么|如何|实践|搭建|实现|入门|教程|指南|方法|配置|使用", re.I)),
    ("观点/思考", re.compile(r"思考|为什么|应该|需要|不是|本质|未来|趋势|时代|方向", re.I)),
    ("环境/踩坑", re.compile(r"环境|搭建|安装|配置|WSL|黑苹果|Manjaro|Windows|JDK|IDEA|PVE|Samba|Tailscale|Mutagen", re.I)),
]


def _to_int(value, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _format_date(timestamp: int | None) -> str:
    if not timestamp:
        return "未知日期"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def _normalize_articles(article_stats: Iterable[dict]) -> list[dict]:
    return [
        {
            "title": item.get("title") or "未命名文章",
            "date": _format_date(_to_int(item.get("publish_time"), 0)),
            "hour": datetime.fromtimestamp(_to_int(item.get("publish_time"), 0)).hour
            if item.get("publish_time")
            else None,
            "itemidx": _to_int(item.get("itemidx"), 1),
            "read_num": _to_int(item.get("read_num")),
            "like_num": _to_int(item.get("like_num")) + _to_int(item.get("old_like_num")),
            "content_url": item.get("content_url") or "",
            "title_length": _to_int(item.get("title_length"), len(item.get("title") or "")),
            "digest": item.get("digest") or "",
            "digest_length": _to_int(item.get("digest_length"), len(item.get("digest") or "")),
            "has_cover": bool(item.get("has_cover") or item.get("cover") or item.get("cover_16_9") or item.get("cover_235_1")),
        }
        for item in article_stats
    ]


def _number_stats(values: list[int]) -> dict:
    if not values:
        return {"count": 0, "avg": 0, "median": 0, "max": 0, "min": 0}
    return {
        "count": len(values),
        "avg": round(sum(values) / len(values), 2),
        "median": median(values),
        "max": max(values),
        "min": min(values),
    }


def _bucket_length(value: int, buckets: list[tuple[int, int | None, str]]) -> str:
    for start, end, label in buckets:
        if value >= start and (end is None or value <= end):
            return label
    return "未知"


def _group_by(rows: list[dict], key: str) -> list[dict]:
    groups: dict[object, list[dict]] = {}
    for row in rows:
        group_key = row.get(key)
        if group_key is not None:
            groups.setdefault(group_key, []).append(row)
    return [
        {
            key: group_key,
            "count": len(items),
            "avg_read": round(sum(item["read_num"] for item in items) / len(items), 2),
            "avg_like": round(sum(item["like_num"] for item in items) / len(items), 2),
        }
        for group_key, items in sorted(groups.items(), key=lambda pair: pair[0])
    ]


def _length_group(rows: list[dict], key: str, buckets: list[tuple[int, int | None, str]]) -> list[dict]:
    grouped_rows = [{**row, "bucket": _bucket_length(_to_int(row.get(key)), buckets)} for row in rows]
    bucket_order = {label: index for index, (_, _, label) in enumerate(buckets)}
    return sorted(_group_by(grouped_rows, "bucket"), key=lambda row: bucket_order.get(row["bucket"], 999))


def _topic_groups(rows: list[dict]) -> list[dict]:
    def build_group(name: str, pattern: re.Pattern) -> dict:
        items = [row for row in rows if pattern.search(row["title"])]
        return {
            "name": name,
            "count": len(items),
            "avg_read": round(sum(item["read_num"] for item in items) / len(items), 2) if items else 0,
            "avg_like": round(sum(item["like_num"] for item in items) / len(items), 2) if items else 0,
            "top_titles": sorted(items, key=lambda item: item["read_num"], reverse=True)[:5],
        }

    return [build_group(name, pattern) for name, pattern in TOPIC_PATTERNS]


def _markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    if not rows:
        return "暂无数据"
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _recommend_topics(topic_groups: list[dict]) -> list[str]:
    effective_groups = [group for group in topic_groups if group["count"] > 0]
    best_groups = sorted(effective_groups, key=lambda group: group["avg_read"], reverse=True)[:3]
    base = [
        f"继续加码「{group['name']}」方向：历史平均阅读约 {group['avg_read']}，优先写具体场景、具体工具、具体问题。"
        for group in best_groups
    ]
    return [
        *base,
        "减少纯观点式标题，尽量把观点包装成一次可复现的实践、踩坑或方案对比。",
        "标题建议采用「弃用 X，用 Y 解决 Z」「为什么 X 后 Y 仍然不对」「我的 X 配置清单」这类强问题结构。",
    ]


def generate_analysis_report(
    article_stats: list[dict],
    fans_summary: dict | None = None,
    total_fans: int | None = None,
) -> str:
    """生成公众号文章表现 Markdown 分析报告。"""
    rows = _normalize_articles(article_stats)
    read_stats = _number_stats([row["read_num"] for row in rows])
    like_stats = _number_stats([row["like_num"] for row in rows])
    top_read = sorted(rows, key=lambda row: row["read_num"], reverse=True)[:10]
    top_like = sorted(rows, key=lambda row: row["like_num"], reverse=True)[:10]
    by_position = _group_by(rows, "itemidx")
    by_hour = sorted(_group_by(rows, "hour"), key=lambda row: row["avg_read"], reverse=True)[:8]
    by_title_length = _length_group(
        rows,
        "title_length",
        [(0, 10, "0-10"), (11, 18, "11-18"), (19, 26, "19-26"), (27, 36, "27-36"), (37, None, "37+")],
    )
    by_digest_length = _length_group(
        rows,
        "digest_length",
        [(0, 0, "无摘要"), (1, 40, "1-40"), (41, 80, "41-80"), (81, 140, "81-140"), (141, None, "141+")],
    )
    topic_groups = _topic_groups(rows)
    topic_table_rows = sorted(topic_groups, key=lambda row: row["avg_read"], reverse=True)
    recent_rows = sorted(rows, key=lambda row: row["date"], reverse=True)[:10]

    fans_lines = []
    if fans_summary:
        net_gain = fans_summary.get("net_gain", [])
        new_user = fans_summary.get("new_user", [])
        cancel_user = fans_summary.get("cancel_user", [])
        fans_lines = [
            f"- 当前总粉丝：{total_fans if total_fans is not None else '未知'}",
            f"- 区间新增：{sum(_to_int(value) for value in new_user)}",
            f"- 区间取关：{sum(_to_int(value) for value in cancel_user)}",
            f"- 区间净增：{sum(_to_int(value) for value in net_gain)}",
        ]

    report_lines = [
        "# 公众号文章表现分析报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 总览",
        "",
        f"- 文章样本数：{read_stats['count']}",
        f"- 阅读数：平均 {read_stats['avg']}，中位数 {read_stats['median']}，最高 {read_stats['max']}，最低 {read_stats['min']}",
        f"- 赞/在看：平均 {like_stats['avg']}，中位数 {like_stats['median']}，最高 {like_stats['max']}",
        *fans_lines,
        "",
        "## 阅读 Top 10",
        "",
        _markdown_table(
            ["阅读", "赞/在看", "位置", "发布时间", "标题"],
            [[row["read_num"], row["like_num"], row["itemidx"], row["date"], row["title"]] for row in top_read],
        ),
        "",
        "## 互动 Top 10",
        "",
        _markdown_table(
            ["赞/在看", "阅读", "位置", "发布时间", "标题"],
            [[row["like_num"], row["read_num"], row["itemidx"], row["date"], row["title"]] for row in top_like],
        ),
        "",
        "## 主题表现",
        "",
        _markdown_table(
            ["主题", "样本数", "平均阅读", "平均赞/在看"],
            [[row["name"], row["count"], row["avg_read"], row["avg_like"]] for row in topic_table_rows],
        ),
        "",
        "## 位置表现",
        "",
        _markdown_table(
            ["位置", "样本数", "平均阅读", "平均赞/在看"],
            [[row["itemidx"], row["count"], row["avg_read"], row["avg_like"]] for row in by_position],
        ),
        "",
        "## 标题与摘要表现",
        "",
        "### 标题长度",
        "",
        _markdown_table(
            ["标题长度", "样本数", "平均阅读", "平均赞/在看"],
            [[row["bucket"], row["count"], row["avg_read"], row["avg_like"]] for row in by_title_length],
        ),
        "",
        "### 摘要长度",
        "",
        _markdown_table(
            ["摘要长度", "样本数", "平均阅读", "平均赞/在看"],
            [[row["bucket"], row["count"], row["avg_read"], row["avg_like"]] for row in by_digest_length],
        ),
        "",
        "## 发布时间表现",
        "",
        _markdown_table(
            ["小时", "样本数", "平均阅读", "平均赞/在看"],
            [[row["hour"], row["count"], row["avg_read"], row["avg_like"]] for row in by_hour],
        ),
        "",
        "## 最近文章",
        "",
        _markdown_table(
            ["阅读", "赞/在看", "位置", "发布时间", "标题"],
            [[row["read_num"], row["like_num"], row["itemidx"], row["date"], row["title"]] for row in recent_rows],
        ),
        "",
        "## 下次优化建议",
        "",
        *[f"- {item}" for item in _recommend_topics(topic_groups)],
        "- 优先把重点文章放头条；二条/三条更适合作为补充或系列延展。",
        "- 优先测试上午 9-10 点、下午 16 点附近发布，但要结合后续更多样本继续验证。",
        "",
        "## 下次可写方向",
        "",
        "- 远程开发/本地开发环境：继续写具体工具组合、配置清单和踩坑复盘。",
        "- AI 编码工作流：避免空泛观点，改成实测对比、提示词流程、失败案例复盘。",
        "- 微信/小程序/前端工程化：保持问题导向，突出可复制步骤和最终收益。",
    ]
    return "\n".join(report_lines) + "\n"
