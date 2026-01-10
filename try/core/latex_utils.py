"""
LaTeX公式处理工具
用于在翻译过程中保护LaTeX公式不被翻译
"""
import re
from typing import Tuple, Dict

# LaTeX公式的正则表达式模式
LATEX_PATTERNS = [
    r'\$[^$]+\$',  # 行内公式 $...$
    r'\$\$[^$]+\$\$',  # 块级公式 $$...$$
    r'\\\[.*?\\\]',  # \[...\]
    r'\\\(.*?\\\)',  # \(...\)
    r'\\begin\{[^}]+\}.*?\\end\{[^}]+\}',  # \begin{...}...\end{...}
]


def extract_latex(text: str) -> Tuple[str, Dict[str, str]]:
    """
    从文本中提取LaTeX公式，用占位符替换
    
    Args:
        text: 包含LaTeX公式的文本
    
    Returns:
        (清理后的文本, 公式字典 {占位符: 原始公式})
    """
    latex_dict = {}
    cleaned_text = text
    placeholder_counter = 0
    
    # 按顺序匹配所有LaTeX公式
    for pattern in LATEX_PATTERNS:
        matches = re.finditer(pattern, cleaned_text, re.DOTALL)
        # 需要从后往前替换，避免索引变化
        matches_list = list(matches)
        for match in reversed(matches_list):
            placeholder = f"__LATEX_PLACEHOLDER_{placeholder_counter}__"
            latex_dict[placeholder] = match.group(0)
            cleaned_text = cleaned_text[:match.start()] + placeholder + cleaned_text[match.end():]
            placeholder_counter += 1
    
    return cleaned_text, latex_dict


def restore_latex(text: str, latex_dict: Dict[str, str]) -> str:
    """
    将占位符替换回原始LaTeX公式
    
    Args:
        text: 包含占位符的文本
        latex_dict: 公式字典 {占位符: 原始公式}
    
    Returns:
        恢复LaTeX公式后的文本
    """
    restored_text = text
    for placeholder, latex_formula in latex_dict.items():
        restored_text = restored_text.replace(placeholder, latex_formula)
    
    return restored_text


def has_latex(text: str) -> bool:
    """
    检查文本是否包含LaTeX公式
    
    Args:
        text: 待检查的文本
    
    Returns:
        是否包含LaTeX公式
    """
    for pattern in LATEX_PATTERNS:
        if re.search(pattern, text):
            return True
    return False

