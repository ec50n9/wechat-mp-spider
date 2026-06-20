"""通用工具函数。"""

import csv
import html as html_module
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def extract_token_from_url(url: str) -> str | None:
    """从 URL 查询参数中提取 token。"""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    return qs.get("token", [None])[0]


def save_json(data, path: Path) -> None:
    """保存数据为 JSON 文件。"""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_csv(items: list[dict], path: Path) -> None:
    """把字典列表保存为 CSV，嵌套结构会被拍平。"""
    if not items:
        path.write_text("", encoding="utf-8")
        return

    keys = set()
    flat_items = []
    for item in items:
        flat = flatten_dict(item)
        keys.update(flat.keys())
        flat_items.append(flat)

    keys = sorted(keys)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(flat_items)


def flatten_dict(d: dict, parent_key: str = "", sep: str = ".") -> dict:
    """把嵌套字典拍平。"""
    items: list[tuple[str, str]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else str(k)
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep).items())
        elif isinstance(v, list):
            items.append((new_key, json.dumps(v, ensure_ascii=False)))
        else:
            items.append((new_key, str(v) if v is not None else ""))
    return dict(items)


def unescape_json_string(s: str) -> dict:
    """对 HTML 转义后的 JSON 字符串做反转义并解析。"""
    return json.loads(html_module.unescape(s))
