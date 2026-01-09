from ebooklib import epub
from bs4 import BeautifulSoup
import json
from pathlib import Path

# def split_epub_by_chapter(epub_path):
#     """加载EPUB并提取章节结构化的内容"""
#     book = epub.read_epub(epub_path)
#     chapters = [] # 存储结果

#     # 1. 获取目录项
#     toc_items = book.toc # 这是一个层级化的目录列表

#     # 2. 遍历目录，提取每个章节
#     def process_items(items, level=0):
#         for item in items:
#             if isinstance(item, tuple) or isinstance(item, list):
#                 # 递归处理子章节
#                 process_items(item, level+1)
#             else:
#                 # item 是一个 ebooklib.epub.Link 对象
#                 chapter = {}
#                 chapter['title'] = item.title
#                 chapter['level'] = level
#                 # 3. 通过 item.href 找到对应的文档内容
#                 doc = book.get_item_with_href(item.href)
#                 if doc:
#                     # 4. 解析HTML内容，提取纯文本
#                     soup = BeautifulSoup(doc.content, 'html.parser')
#                     # 移除脚本、样式等标签
#                     for tag in soup(["script", "style", "nav"]):
#                         tag.decompose()
#                     # 获取文本，可按段落维护
#                     text = soup.get_text(separator='\n', strip=True)
#                     # 或者保留段落结构
#                     # paragraphs = [p.get_text() for p in soup.find_all('p')]
#                     chapter['content'] = text
#                     chapters.append(chapter)

#     process_items(toc_items)
#     return chapters

def split_epub_by_chapter(json_path):
    """从 JSON 文件加载章节结构化的内容"""
    json_path = Path(json_path)
    if not json_path.exists():
        raise FileNotFoundError(f"JSON 文件不存在: {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        chapters = json.load(f)
    
    return chapters

def split_chapter_into_chunks(
    chapter_text: str,
    max_chars: int = 1200,
    overlap: int = 200
):
    """
    将章节文本切分为可翻译 chunks
    - max_chars：单 chunk 最大字符数（粗略 ≈ 400 tokens）
    - overlap：上下文重叠，防止断义
    """
    paragraphs = chapter_text.split("\n")
    chunks = []

    current = ""
    for p in paragraphs:
        if len(current) + len(p) <= max_chars:
            current += p + "\n"
        else:
            chunks.append(current.strip())
            current = current[-overlap:] + p + "\n"

    if current.strip():
        chunks.append(current.strip())

    return chunks
