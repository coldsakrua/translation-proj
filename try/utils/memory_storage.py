"""
翻译记忆存储管理模块
用于保存和加载已翻译的文本对，支持跨章节的上下文传递
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime


# 翻译记忆库文件路径（按书籍组织）
# 章节摘要文件路径（按书籍组织，在函数中动态生成）


def load_translation_memory(book_id: str, memory_file: Optional[str] = None) -> Dict[str, dict]:
    """
    加载翻译记忆库
    
    Args:
        book_id: 书籍ID
        memory_file: 记忆库文件路径，如果为None则使用默认路径（按书籍组织）
    
    Returns:
        字典，key为chunk的唯一标识，value为翻译记忆
    """
    if memory_file is None:
        memory_file = f"output/{book_id}/translation_memory.json"
    
    # 确保目录存在
    os.makedirs(os.path.dirname(memory_file), exist_ok=True)
    
    if not os.path.exists(memory_file):
        return {}
    
    try:
        with open(memory_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            else:
                return {}
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️  加载翻译记忆库失败: {e}")
        return {}


def save_translation_memory(
    book_id: str,
    chapter_id: int,
    chunk_id: int,
    source_text: str,
    translation: str,
    quality_score: Optional[float] = None,
    memory_file: Optional[str] = None
):
    """
    保存翻译记忆到记忆库
    
    Args:
        book_id: 书籍ID
        chapter_id: 章节ID
        chunk_id: chunk ID
        source_text: 原文
        translation: 译文
        quality_score: 质量评分
        memory_file: 记忆库文件路径
    """
    if memory_file is None:
        memory_file = f"output/{book_id}/translation_memory.json"
    
    # 确保目录存在
    os.makedirs(os.path.dirname(memory_file), exist_ok=True)
    
    # 加载现有记忆库
    memory = load_translation_memory(book_id, memory_file)
    
    # 生成唯一标识
    memory_key = f"{book_id}_ch{chapter_id}_ck{chunk_id}"
    
    # 保存翻译记忆
    memory[memory_key] = {
        "book_id": book_id,
        "chapter_id": chapter_id,
        "chunk_id": chunk_id,
        "source_text": source_text,
        "translation": translation,
        "quality_score": quality_score,
        "saved_at": datetime.now().isoformat()
    }
    
    # 保存到文件
    try:
        with open(memory_file, 'w', encoding='utf-8') as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"⚠️  保存翻译记忆库失败: {e}")


def get_chapter_translation_memory(
    book_id: str,
    chapter_id: int,
    memory_file: Optional[str] = None
) -> List[dict]:
    """
    获取指定章节的所有翻译记忆
    
    Args:
        book_id: 书籍ID
        chapter_id: 章节ID
        memory_file: 记忆库文件路径
    
    Returns:
        该章节的翻译记忆列表
    """
    memory = load_translation_memory(book_id, memory_file)
    
    chapter_memories = []
    for key, value in memory.items():
        if (value.get('book_id') == book_id and 
            value.get('chapter_id') == chapter_id):
            chapter_memories.append(value)
    
    # 按chunk_id排序
    chapter_memories.sort(key=lambda x: x.get('chunk_id', 0))
    return chapter_memories


def get_previous_chapters_memory(
    book_id: str,
    current_chapter_id: int,
    top_k: int = 5,
    memory_file: Optional[str] = None
) -> List[dict]:
    """
    获取之前章节的翻译记忆（用于上下文传递）
    
    Args:
        book_id: 书籍ID
        current_chapter_id: 当前章节ID
        top_k: 返回最近k个chunk的翻译记忆
        memory_file: 记忆库文件路径
    
    Returns:
        之前章节的翻译记忆列表（按时间倒序，最多top_k个）
    """
    memory = load_translation_memory(book_id, memory_file)
    
    previous_memories = []
    for key, value in memory.items():
        if (value.get('book_id') == book_id and 
            value.get('chapter_id') < current_chapter_id):
            previous_memories.append(value)
    
    # 按章节和chunk排序，取最近的
    previous_memories.sort(
        key=lambda x: (x.get('chapter_id', 0), x.get('chunk_id', 0)),
        reverse=True
    )
    
    return previous_memories[:top_k]


def get_similar_translation_examples(
    source_text: str,
    book_id: str,
    top_k: int = 3,
    memory_file: Optional[str] = None
) -> List[dict]:
    """
    从翻译记忆中检索与当前文本相似的翻译示例
    
    Args:
        source_text: 当前原文
        book_id: 书籍ID
        top_k: 返回最相似的k个示例
        memory_file: 记忆库文件路径
    
    Returns:
        相似的翻译示例列表
    """
    memory = load_translation_memory(book_id, memory_file)
    
    # 简单的相似度匹配：基于关键词重叠
    source_words = set(source_text.lower().split())
    
    examples = []
    for key, value in memory.items():
        if value.get('book_id') != book_id:
            continue
        
        example_words = set(value.get('source_text', '').lower().split())
        # 计算Jaccard相似度
        intersection = len(source_words & example_words)
        union = len(source_words | example_words)
        similarity = intersection / union if union > 0 else 0
        
        if similarity > 0.1:  # 至少10%的词汇重叠
            examples.append({
                **value,
                'similarity': similarity
            })
    
    # 按相似度排序
    examples.sort(key=lambda x: x.get('similarity', 0), reverse=True)
    return examples[:top_k]


def load_chapter_summaries(book_id: str, summary_file: Optional[str] = None) -> Dict[str, dict]:
    """
    加载章节摘要
    
    Args:
        book_id: 书籍ID
        summary_file: 摘要文件路径
    
    Returns:
        字典，key为章节标识，value为摘要信息
    """
    if summary_file is None:
        summary_file = f"output/{book_id}/chapter_summaries.json"
    
    os.makedirs(os.path.dirname(summary_file), exist_ok=True)
    
    if not os.path.exists(summary_file):
        return {}
    
    try:
        with open(summary_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️  加载章节摘要失败: {e}")
        return {}


def save_chapter_summary(
    book_id: str,
    chapter_id: int,
    summary: str,
    key_points: List[str],
    summary_file: Optional[str] = None
):
    """
    保存章节摘要
    
    Args:
        book_id: 书籍ID
        chapter_id: 章节ID
        summary: 摘要文本
        key_points: 关键点列表
        summary_file: 摘要文件路径
    """
    if summary_file is None:
        summary_file = f"output/{book_id}/chapter_summaries.json"
    
    os.makedirs(os.path.dirname(summary_file), exist_ok=True)
    
    summaries = load_chapter_summaries(book_id, summary_file)
    
    chapter_key = f"{book_id}_ch{chapter_id}"
    summaries[chapter_key] = {
        "book_id": book_id,
        "chapter_id": chapter_id,
        "summary": summary,
        "key_points": key_points,
        "created_at": datetime.now().isoformat()
    }
    
    try:
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summaries, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"⚠️  保存章节摘要失败: {e}")


def get_previous_chapter_summaries(
    book_id: str,
    current_chapter_id: int,
    summary_file: Optional[str] = None
) -> List[dict]:
    """
    获取之前章节的摘要
    
    Args:
        book_id: 书籍ID
        current_chapter_id: 当前章节ID
        summary_file: 摘要文件路径
    
    Returns:
        之前章节的摘要列表
    """
    summaries = load_chapter_summaries(book_id, summary_file)
    
    previous_summaries = []
    for key, value in summaries.items():
        if (value.get('book_id') == book_id and 
            value.get('chapter_id') < current_chapter_id):
            previous_summaries.append(value)
    
    # 按章节ID排序
    previous_summaries.sort(key=lambda x: x.get('chapter_id', 0))
    return previous_summaries

