"""
术语存储管理模块
用于保存和加载已审查的术语，避免重复审查
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

# 全局术语库文件路径（相对于项目根目录）
# 使用相对路径，从 try/ 目录运行
GLOBAL_GLOSSARY_FILE = "output/reviewed_glossary.json"


def load_reviewed_glossary(glossary_file: Optional[str] = None) -> Dict[str, dict]:
    """
    加载已审查的术语库
    
    Args:
        glossary_file: 术语库文件路径，如果为None则使用默认路径
    
    Returns:
        字典，key为术语的src，value为术语信息
    """
    if glossary_file is None:
        glossary_file = GLOBAL_GLOSSARY_FILE
    
    # 确保目录存在
    os.makedirs(os.path.dirname(glossary_file), exist_ok=True)
    
    if not os.path.exists(glossary_file):
        return {}
    
    try:
        with open(glossary_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 如果文件是列表格式，转换为字典格式
            if isinstance(data, list):
                return {term.get('src', ''): term for term in data if term.get('src')}
            elif isinstance(data, dict):
                return data
            else:
                return {}
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️  加载术语库失败: {e}")
        return {}


def save_reviewed_glossary(reviewed_terms: List[dict], glossary_file: Optional[str] = None):
    """
    保存已审查的术语到术语库
    
    Args:
        reviewed_terms: 已审查的术语列表
        glossary_file: 术语库文件路径，如果为None则使用默认路径
    """
    if glossary_file is None:
        glossary_file = GLOBAL_GLOSSARY_FILE
    
    # 确保目录存在
    os.makedirs(os.path.dirname(glossary_file), exist_ok=True)
    
    # 加载现有术语库
    existing_glossary = load_reviewed_glossary(glossary_file)
    
    # 更新或添加新审查的术语
    for term in reviewed_terms:
        src = term.get('src', '')
        if src:
            # 添加审查时间戳（如果还没有）
            if 'reviewed_at' not in term:
                from datetime import datetime
                term['reviewed_at'] = datetime.now().isoformat()
            existing_glossary[src] = term
    
    # 保存到文件
    try:
        with open(glossary_file, 'w', encoding='utf-8') as f:
            json.dump(existing_glossary, f, ensure_ascii=False, indent=2)
        print(f"✅ 已保存 {len(reviewed_terms)} 个术语到术语库: {glossary_file}")
    except IOError as e:
        print(f"⚠️  保存术语库失败: {e}")


def filter_reviewed_terms(terms: List[dict], glossary_file: Optional[str] = None) -> tuple[List[dict], List[dict]]:
    """
    过滤术语列表，分离出已审查和未审查的术语
    
    Args:
        terms: 待审查的术语列表
        glossary_file: 术语库文件路径
    
    Returns:
        (已审查的术语列表, 未审查的术语列表)
    """
    reviewed_glossary = load_reviewed_glossary(glossary_file)
    
    reviewed_terms = []
    unreviewed_terms = []
    
    for term in terms:
        src = term.get('src', '')
        if src in reviewed_glossary:
            # 使用已审查的术语信息（保留审查结果）
            reviewed_term = reviewed_glossary[src].copy()
            # 保留当前术语的其他信息（如context_meaning等）
            reviewed_term.update({k: v for k, v in term.items() if k not in reviewed_term})
            # 确保标记为已审查
            reviewed_term['human_reviewed'] = True
            # 如果术语库中没有 human_modified 标记，默认为 False（可能是之前审查时接受的）
            if 'human_modified' not in reviewed_term:
                reviewed_term['human_modified'] = False
            reviewed_terms.append(reviewed_term)
        else:
            unreviewed_terms.append(term)
    
    return reviewed_terms, unreviewed_terms

