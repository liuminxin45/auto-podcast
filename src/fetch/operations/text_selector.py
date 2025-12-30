"""
Text Selector - 优先选择最精简的文本字段用于后续处理

策略：
1. 优先使用 title（如果不是纯日期且有实质内容）
2. 其次使用 summary（如果不是纯日期且有实质内容）
3. 最后使用 content
"""

import re
from typing import Optional


def is_date_only(text: str) -> bool:
    """
    判断文本是否主要是日期
    
    Args:
        text: 待检测文本
        
    Returns:
        bool: True表示主要是日期
    """
    if not text:
        return True
    
    # 移除常见的日期前缀/后缀
    cleaned = text
    for noise in ['每天', '每日', '60秒', '读懂世界', '星期', '周', '📅', ' ', '\t', '\n']:
        cleaned = cleaned.replace(noise, '')
    
    # 检查是否主要是日期格式
    date_patterns = [
        r'^\d{4}[-/年]\d{1,2}[-/月]\d{1,2}',  # 2025-12-30 / 2025年12月30日
        r'^\d{4}\.\d{1,2}\.\d{1,2}',  # 2025.12.30
        r'^\d{1,2}[-/月]\d{1,2}[-/日]',  # 12-30 / 12月30日
    ]
    
    for pattern in date_patterns:
        if re.match(pattern, cleaned):
            # 移除日期后剩余内容很少
            remaining = re.sub(pattern, '', cleaned).strip()
            remaining = re.sub(r'[日号\s\-/\.]', '', remaining)
            if len(remaining) < 5:
                return True
    
    return False


def has_substantial_content(text: str, min_length: int = 10) -> bool:
    """
    判断文本是否有实质内容
    
    Args:
        text: 待检测文本
        min_length: 最小有效长度
        
    Returns:
        bool: True表示有实质内容
    """
    if not text:
        return False
    
    # 移除空白字符后检查长度
    cleaned = text.strip()
    if len(cleaned) < min_length:
        return False
    
    # 检查是否主要是日期
    if is_date_only(cleaned):
        return False
    
    return True


def select_best_text(
    title: Optional[str],
    summary: Optional[str],
    content: Optional[str],
    min_length: int = 10
) -> tuple[str, str]:
    """
    选择最佳的文本字段用于后续处理
    
    优先级：title > summary > content
    
    Args:
        title: 标题
        summary: 摘要
        content: 正文
        min_length: 最小有效长度
        
    Returns:
        (selected_text, source_field): 选中的文本和来源字段名
    """
    # 1. 优先使用 title
    if title and has_substantial_content(title, min_length):
        return title.strip(), "title"
    
    # 2. 其次使用 summary
    if summary and has_substantial_content(summary, min_length):
        return summary.strip(), "summary"
    
    # 3. 最后使用 content
    if content and content.strip():
        return content.strip(), "content"
    
    # 4. 降级：如果都没有实质内容，返回任何非空字段
    for text, field in [(title, "title"), (summary, "summary"), (content, "content")]:
        if text and text.strip():
            return text.strip(), field
    
    return "", "none"


def simplify_item(item: dict) -> dict:
    """
    简化 item，只保留必要字段，并选择最佳文本字段
    
    Args:
        item: 原始 item 字典
        
    Returns:
        dict: 简化后的 item
    """
    # 选择最佳文本
    title = item.get("title", "")
    summary = item.get("summary", "")
    content = item.get("content", "")
    
    selected_text, text_source = select_best_text(title, summary, content)
    
    # 构建简化的 item
    simplified = {
        "id": item.get("id", ""),
        "source_name": item.get("source_name", ""),
        "source_domain": item.get("source_domain", ""),
        "source_url": item.get("source_url", ""),
        "title": title,
        "text": selected_text,  # 选中的最佳文本
        "text_source": text_source,  # 文本来源字段
        "published_at": item.get("published_at", ""),
        "lang": item.get("lang", "zh"),
        "fingerprints": item.get("fingerprints", {}),
    }
    
    # 保留一些可能有用的元数据
    if "_digest_detection" in item:
        simplified["_digest_detection"] = item["_digest_detection"]
    
    if "_compliance" in item:
        simplified["_compliance"] = item["_compliance"]
    
    return simplified


__all__ = [
    "is_date_only",
    "has_substantial_content",
    "select_best_text",
    "simplify_item",
]
