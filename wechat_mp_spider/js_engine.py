"""简单的 JS 对象转 JSON 工具，用于解析微信后台的非标准 JSON。"""

import json
import re


def js_object_to_json(js_text: str) -> dict:
    """
    把类似 JavaScript 对象字面量的文本转换为 Python dict。

    支持：
    - 无引号 key: { key: value }
    - 单引号字符串: 'value'
    - 数字字符串乘法: '1' * 1
    - 尾部逗号
    """
    text = js_text.strip()

    # 处理 '1' * 1 这种微信常见写法，转成 1
    text = re.sub(r"'([\d.]+)'\s*\*\s*\d+", r"\1", text)

    # 把单引号字符串转成双引号字符串（简单处理，假设没有转义单引号）
    text = _replace_quotes(text)

    # 给无引号的 key 加上双引号
    text = _quote_unquoted_keys(text)

    # 去掉尾部逗号
    text = re.sub(r",\s*(\}|\])", r"\1", text)

    return json.loads(text)


def _replace_quotes(text: str) -> str:
    """把成对单引号包裹的字符串转成双引号。"""
    result = []
    i = 0
    while i < len(text):
        if text[i] == "'":
            # 找到下一个单引号
            end = text.find("'", i + 1)
            if end == -1:
                result.append(text[i])
                i += 1
                continue
            content = text[i + 1 : end]
            # 转义内容中的双引号和反斜杠
            content = content.replace("\\", "\\\\").replace('"', '\\"')
            result.append('"' + content + '"')
            i = end + 1
        else:
            result.append(text[i])
            i += 1
    return "".join(result)


def _quote_unquoted_keys(text: str) -> str:
    """给对象字面量中未加引号的 key 加上双引号。"""
    # 匹配 key: 或 key :，其中 key 是标识符
    # 但要避免把 true/false/null 等值误加引号
    # 这里只处理冒号前面的 key
    result = []
    i = 0
    while i < len(text):
        # 找冒号
        if text[i] == ":":
            # 向前找 key
            j = i - 1
            while j >= 0 and text[j] in " \t\n\r":
                j -= 1
            key_end = j
            while j >= 0 and (text[j].isalnum() or text[j] in "_$"):
                j -= 1
            key_start = j + 1
            key = text[key_start : key_end + 1]

            # 判断是否是合法的未加引号 key
            before_key = text[:key_start].rstrip()
            is_at_object_start = before_key.endswith(("{", ","))

            if key and key not in ("true", "false", "null") and is_at_object_start:
                # 替换 key
                result = list(text[:key_start])
                result.append(f'"{key}"')
                result.append(text[i:])
                text = "".join(result)
                i = key_start + len(f'"{key}"') + 1
                continue
        i += 1
    return text
