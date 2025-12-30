"""
HTML Content Cleaner
"""

import re
from html.parser import HTMLParser


class HTMLTextExtractor(HTMLParser):
    """提取HTML中的纯文本"""
    
    def __init__(self):
        super().__init__()
        self.text_parts = []
    
    def handle_data(self, data):
        self.text_parts.append(data)
    
    def get_text(self):
        return ''.join(self.text_parts)


def clean_html_content(html: str) -> str:
    """
    清洗HTML内容，提取纯文本
    
    Args:
        html: HTML字符串
    
    Returns:
        str: 清洗后的纯文本
    """
    if not html:
        return ""
    
    # 移除script和style标签
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    
    # 移除HTML注释
    html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
    
    # 使用HTMLParser提取文本
    parser = HTMLTextExtractor()
    try:
        parser.feed(html)
        text = parser.get_text()
    except Exception:
        # 降级：使用正则移除所有HTML标签
        text = re.sub(r'<[^>]+>', '', html)
    
    # 移除HTML实体引用的残留
    text = re.sub(r'&[a-zA-Z]+;', '', text)
    text = re.sub(r'&#\d+;', '', text)
    
    # 清理空白字符
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    return text


def remove_english_paragraphs(text: str) -> str:
    """
    移除纯英文段落，保留中文内容
    
    Args:
        text: 文本内容
    
    Returns:
        str: 过滤后的文本
    """
    if not text:
        return ""
    
    # 按段落分割（按换行或句号分割）
    paragraphs = re.split(r'[\n。]', text)
    
    chinese_paragraphs = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # 检查段落中是否包含中文字符
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', para))
        
        if has_chinese:
            chinese_paragraphs.append(para)
    
    return '。'.join(chinese_paragraphs) if chinese_paragraphs else text


def clean_content(content: str, remove_non_chinese: bool = True) -> str:
    """
    综合清洗内容：移除HTML标签、过滤非中文段落
    
    Args:
        content: 原始内容
        remove_non_chinese: 是否移除纯英文段落
    
    Returns:
        str: 清洗后的内容
    """
    if not content:
        return ""
    
    # 1. 清除HTML标签
    text = clean_html_content(content)
    
    # 2. 移除纯英文段落（可选）
    if remove_non_chinese:
        text = remove_english_paragraphs(text)
    
    # 3. 移除常见的版权声明和无用信息
    text = re.sub(r'财富中文网所刊载内容.*?未经许可.*?任何使用。?', '', text, flags=re.DOTALL)
    text = re.sub(r'译者：.*', '', text)
    text = re.sub(r'审校：.*', '', text)
    
    # 4. 最终清理
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    return text
