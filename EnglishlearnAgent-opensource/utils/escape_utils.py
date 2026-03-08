"""
安全转义工具函数
================
用于防止 XSS 和注入攻击

参考：
- Python html.escape: https://docs.python.org/3/library/html.html
- Django json_script: 转义 < > & 为 Unicode 序列防止 </script> 注入
- CSS 类名规范: 只允许字母、数字、连字符、下划线
"""
import html
import json
import re


def escape_html(text: str) -> str:
    """
    HTML 转义（用于 unsafe_allow_html=True 的内容）

    转义 & < > " ' 防止 XSS

    Args:
        text: 要转义的文本

    Returns:
        转义后的安全文本
    """
    if not text:
        return text
    return html.escape(str(text), quote=True)


def escape_js_string(text: str) -> str:
    """
    JS 字符串转义（用于 f-string 拼入 <script> 的内容）

    使用 json.dumps + 转义 HTML 敏感字符，防止 XSS 和 </script> 注入
    参考 Django json_script 实现

    Args:
        text: 要转义的文本

    Returns:
        带引号的安全 JS 字符串，如 "hello"
    """
    if text is None:
        return '""'
    return json.dumps(str(text)).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def escape_html_preserve_br(text: str) -> str:
    """
    HTML 转义，但保留换行符转换为 <br>

    用于需要显示换行的 AI 生成内容

    Args:
        text: 要转义的文本

    Returns:
        转义后的安全文本，换行符被替换为 <br>
    """
    if not text:
        return text
    # 先转义 HTML，再将换行符替换为 <br>
    escaped = html.escape(str(text), quote=True)
    return escaped.replace('\n', '<br>')


def make_safe_css_id(text: str) -> str:
    """
    创建安全的 CSS 类名/HTML id（白名单过滤）

    只保留字母、数字、连字符、下划线
    用于 CSS 类名和 HTML id 属性，防止 CSS/HTML 注入

    Args:
        text: 要处理的文本

    Returns:
        只包含安全字符的标识符
    """
    if not text:
        return text
    # 替换空格为连字符，移除其他不安全字符
    safe = str(text).replace(' ', '-')
    return re.sub(r'[^a-zA-Z0-9_-]', '', safe)
