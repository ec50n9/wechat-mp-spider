"""
在页面内执行的 JS 辅助函数。

微信部分数据通过前端 JS 变量或 ECharts 渲染，需要在页面上下文中读取。
"""

# 读取页面内全局变量
READ_GLOBAL_VARS = """
(vars) => {
    const result = {};
    for (const v of vars) {
        result[v] = window[v] || null;
    }
    return result;
}
"""

# 触发点击，常用于打开详情弹窗
TRIGGER_CLICK = """
(selector) => {
    const el = document.querySelector(selector);
    if (el) {
        el.click();
        return true;
    }
    return false;
}
"""

# 滚动页面到底部
SCROLL_TO_BOTTOM = """
() => {
    window.scrollTo(0, document.body.scrollHeight);
    return document.body.scrollHeight;
}
"""

# 等待指定毫秒
SLEEP_JS = """
(ms) => new Promise(resolve => setTimeout(resolve, ms))
"""
