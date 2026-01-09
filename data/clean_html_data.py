#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
HTML 数据清洗脚本
从 HTML 文件中提取中英文对照内容，转换为 try 目录所需的格式
"""

from bs4 import BeautifulSoup
import re
import json
from pathlib import Path


def clean_text(text):
    """清理文本，移除多余空白和特殊字符"""
    if not text:
        return ""
    # 移除多余的空白字符
    text = re.sub(r'\s+', ' ', text)
    # 移除首尾空白
    text = text.strip()
    return text


def extract_chapters_from_html(html_path):
    """
    从 HTML 文件中提取章节数据
    
    Args:
        html_path: HTML 文件路径
        
    Returns:
        list: 章节列表，每个章节包含 title 和 content
    """
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 移除脚本、样式、导航等不需要的标签
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    
    # 找到文章主体内容
    post_body = soup.find('div', class_='post-body')
    if not post_body:
        # 如果没有找到 post-body，尝试找其他可能的内容容器
        post_body = soup.find('article') or soup.find('main') or soup.find('body')
    
    if not post_body:
        raise ValueError("无法找到文章主体内容")
    
    chapters = []
    current_chapter = None
    current_content = []
    
    # 遍历所有元素
    for element in post_body.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'div']):
        # 跳过图片标签
        if element.name == 'p' and element.find('img'):
            continue
        
        # 跳过链接和元信息段落
        text = element.get_text()
        if any(keyword in text for keyword in ['文章作者', '博客', '声明', '翻译论文汇总', '赏', '打赏']):
            continue
        
        # 如果是标题，开始新章节
        if element.name in ['h1', 'h2', 'h3']:
            # 保存之前的章节
            if current_chapter and current_content:
                current_chapter['content'] = '\n\n'.join(current_content)
                chapters.append(current_chapter)
            
            # 创建新章节
            title = clean_text(text)
            # 提取英文标题（通常是第一个标题）
            if title and not re.search(r'[\u4e00-\u9fff]', title):
                # 这是英文标题
                current_chapter = {
                    'title': title,
                    'level': int(element.name[1]) - 1,  # h1->0, h2->1, h3->2
                    'content': ''
                }
                current_content = []
            elif title and re.search(r'[\u4e00-\u9fff]', title):
                # 这是中文标题，如果当前章节没有标题，使用它
                if not current_chapter:
                    current_chapter = {
                        'title': title,
                        'level': int(element.name[1]) - 1,
                        'content': ''
                    }
                    current_content = []
                # 否则将中文标题也加入内容
                else:
                    current_content.append(title)
        
        # 如果是段落，添加到当前章节内容
        elif element.name == 'p' and text.strip():
            cleaned = clean_text(text)
            if cleaned:
                current_content.append(cleaned)
    
    # 保存最后一个章节
    if current_chapter and current_content:
        current_chapter['content'] = '\n\n'.join(current_content)
        chapters.append(current_chapter)
    
    # 过滤掉空章节
    chapters = [ch for ch in chapters if ch.get('content', '').strip()]
    
    return chapters


def extract_chapters_alternating(html_path):
    """
    按照中英文交替的模式提取
    格式：英文标题 -> 英文内容 -> 中文标题 -> 中文内容 -> 下一个英文标题...
    """
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 移除不需要的标签
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    
    post_body = soup.find('div', class_='post-body')
    if not post_body:
        post_body = soup.find('article') or soup.find('main') or soup.find('body')
    
    if not post_body:
        raise ValueError("无法找到文章主体内容")
    
    chapters = []
    elements = []
    
    # 收集所有文本元素
    for element in post_body.find_all(['h1', 'h2', 'h3', 'h4', 'p']):
        # 跳过图片和元信息
        if element.find('img'):
            continue
        text = element.get_text().strip()
        if not text or any(kw in text for kw in ['文章作者', '博客', '声明', '翻译论文汇总', '赏', '打赏']):
            continue
        
        # 判断是否为中文（包含中文字符）
        is_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
        
        elements.append({
            'tag': element.name,
            'text': clean_text(text),
            'is_chinese': is_chinese
        })
    
    # 按照标题分组，合并中英文内容
    current_en_title = None
    current_zh_title = None
    current_en_content = []
    current_zh_content = []
    current_level = 0
    
    i = 0
    while i < len(elements):
        elem = elements[i]
        
        # 如果是标题
        if elem['tag'] in ['h1', 'h2', 'h3']:
            # 如果遇到新的英文标题，保存之前的章节
            if not elem['is_chinese']:
                # 保存之前的章节
                if current_en_title or current_zh_title:
                    content_parts = []
                    if current_en_title:
                        content_parts.append(f"[EN] {current_en_title}")
                    if current_en_content:
                        content_parts.extend([f"[EN] {p}" for p in current_en_content])
                    if current_zh_title:
                        content_parts.append(f"[ZH] {current_zh_title}")
                    if current_zh_content:
                        content_parts.extend([f"[ZH] {p}" for p in current_zh_content])
                    
                    if content_parts:
                        chapters.append({
                            'title': current_en_title or current_zh_title or f"Section {len(chapters) + 1}",
                            'level': current_level,
                            'content': '\n\n'.join(content_parts)
                        })
                
                # 开始新章节
                current_en_title = elem['text']
                current_zh_title = None
                current_en_content = []
                current_zh_content = []
                current_level = 0 if elem['tag'] == 'h1' else (1 if elem['tag'] == 'h2' else 2)
            
            elif elem['is_chinese']:
                # 中文标题
                current_zh_title = elem['text']
        
        # 如果是段落
        elif elem['tag'] == 'p':
            if elem['is_chinese']:
                current_zh_content.append(elem['text'])
            else:
                current_en_content.append(elem['text'])
        
        i += 1
    
    # 保存最后一个章节
    if current_en_title or current_zh_title:
        content_parts = []
        if current_en_title:
            content_parts.append(f"[EN] {current_en_title}")
        if current_en_content:
            content_parts.extend([f"[EN] {p}" for p in current_en_content])
        if current_zh_title:
            content_parts.append(f"[ZH] {current_zh_title}")
        if current_zh_content:
            content_parts.extend([f"[ZH] {p}" for p in current_zh_content])
        
        if content_parts:
            chapters.append({
                'title': current_en_title or current_zh_title or f"Section {len(chapters) + 1}",
                'level': current_level,
                'content': '\n\n'.join(content_parts)
            })
    
    return chapters


def save_chapters_json(chapters, output_path):
    """保存章节数据为 JSON 文件"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(chapters, f, ensure_ascii=False, indent=2)
    print(f"✅ 已保存 {len(chapters)} 个章节到: {output_path}")


def remove_newlines(text):
    """去掉换行符，将 \n 替换为空格"""
    if not text:
        return ""
    # 将多个连续的换行符替换为单个空格
    text = re.sub(r'\n+', ' ', text)
    # 将多个连续空格替换为单个空格
    text = re.sub(r' +', ' ', text)
    return text.strip()


def separate_en_zh_chapters(html_path):
    """
    分离中英文章节，分别提取英文和中文内容
    返回: (en_chapters, zh_chapters)
    """
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 移除不需要的标签
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    
    post_body = soup.find('div', class_='post-body')
    if not post_body:
        post_body = soup.find('article') or soup.find('main') or soup.find('body')
    
    if not post_body:
        raise ValueError("无法找到文章主体内容")
    
    en_chapters = []
    zh_chapters = []
    elements = []
    
    # 收集所有文本元素
    for element in post_body.find_all(['h1', 'h2', 'h3', 'h4', 'p']):
        # 跳过图片和元信息
        if element.find('img'):
            continue
        text = element.get_text().strip()
        if not text or any(kw in text for kw in ['文章作者', '博客', '声明', '翻译论文汇总', '赏', '打赏']):
            continue
        
        # 判断是否为中文（包含中文字符）
        is_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
        
        elements.append({
            'tag': element.name,
            'text': clean_text(text),
            'is_chinese': is_chinese
        })
    
    # 按照标题分组，分别收集中英文内容
    current_en_title = None
    current_zh_title = None
    current_en_content = []
    current_zh_content = []
    current_level = 0
    skip_references = False  # 标记是否遇到参考文献部分
    seen_en_titles = set()  # 记录已见过的英文标题，用于去重
    seen_zh_titles = set()  # 记录已见过的中文标题，用于去重
    
    i = 0
    while i < len(elements):
        elem = elements[i]
        
        # 如果是标题
        if elem['tag'] in ['h1', 'h2', 'h3']:
            # 检查是否是参考文献标题
            title_text = elem['text'].strip().lower()
            if 'reference' in title_text:
                skip_references = True
                # 保存之前的章节（如果有）
                if current_en_title or current_zh_title:
                    if current_en_title and current_en_title not in seen_en_titles:
                        en_content = ' '.join([current_en_title] + current_en_content) if current_en_content else current_en_title
                        en_content = remove_newlines(en_content)
                        en_chapters.append({
                            'title': remove_newlines(current_en_title),
                            'level': current_level,
                            'content': en_content
                        })
                        seen_en_titles.add(current_en_title)
                    if current_zh_title and current_zh_title not in seen_zh_titles:
                        zh_content = ' '.join([current_zh_title] + current_zh_content) if current_zh_content else current_zh_title
                        zh_content = remove_newlines(zh_content)
                        zh_chapters.append({
                            'title': remove_newlines(current_zh_title),
                            'level': current_level,
                            'content': zh_content
                        })
                        seen_zh_titles.add(current_zh_title)
                # 跳过参考文献部分
                break
            
            # 如果遇到新的英文标题，保存之前的章节
            if not elem['is_chinese']:
                # 保存之前的章节
                if current_en_title or current_zh_title:
                    # 保存英文章节（去重）
                    if current_en_title and current_en_title not in seen_en_titles:
                        en_content = ' '.join([current_en_title] + current_en_content) if current_en_content else current_en_title
                        en_content = remove_newlines(en_content)  # 去掉换行符
                        en_chapters.append({
                            'title': remove_newlines(current_en_title),
                            'level': current_level,
                            'content': en_content
                        })
                        seen_en_titles.add(current_en_title)
                    
                    # 保存中文章节（去重）
                    if current_zh_title and current_zh_title not in seen_zh_titles:
                        zh_content = ' '.join([current_zh_title] + current_zh_content) if current_zh_content else current_zh_title
                        zh_content = remove_newlines(zh_content)  # 去掉换行符
                        zh_chapters.append({
                            'title': remove_newlines(current_zh_title),
                            'level': current_level,
                            'content': zh_content
                        })
                        seen_zh_titles.add(current_zh_title)
                
                # 检查新标题是否已存在，如果存在则跳过
                new_title = elem['text']
                if new_title in seen_en_titles:
                    # 标题已存在，跳过这个章节
                    current_en_title = None
                    current_zh_title = None
                    current_en_content = []
                    current_zh_content = []
                else:
                    # 开始新章节
                    current_en_title = new_title
                    current_zh_title = None
                    current_en_content = []
                    current_zh_content = []
                    current_level = 0 if elem['tag'] == 'h1' else (1 if elem['tag'] == 'h2' else 2)
            
            elif elem['is_chinese']:
                # 中文标题
                new_zh_title = elem['text']
                if new_zh_title in seen_zh_titles:
                    # 标题已存在，跳过
                    current_zh_title = None
                    current_zh_content = []
                else:
                    current_zh_title = new_zh_title
        
        # 如果是段落，且不在参考文献部分
        elif elem['tag'] == 'p' and not skip_references:
            if elem['is_chinese']:
                current_zh_content.append(elem['text'])
            else:
                current_en_content.append(elem['text'])
        
        i += 1
    
    # 保存最后一个章节（去重）
    if current_en_title and current_en_title not in seen_en_titles:
        en_content = ' '.join([current_en_title] + current_en_content) if current_en_content else current_en_title
        en_content = remove_newlines(en_content)  # 去掉换行符
        en_chapters.append({
            'title': remove_newlines(current_en_title),
            'level': current_level,
            'content': en_content
        })
        seen_en_titles.add(current_en_title)
    
    if current_zh_title and current_zh_title not in seen_zh_titles:
        zh_content = ' '.join([current_zh_title] + current_zh_content) if current_zh_content else current_zh_title
        zh_content = remove_newlines(zh_content)  # 去掉换行符
        zh_chapters.append({
            'title': remove_newlines(current_zh_title),
            'level': current_level,
            'content': zh_content
        })
        seen_zh_titles.add(current_zh_title)
    
    return en_chapters, zh_chapters


def main():
    """主函数"""
    html_path = Path(__file__).parent / "1.html"
    output_en = Path(__file__).parent / "1_en.json"
    output_zh = Path(__file__).parent / "1_ch.json"
    
    print(f"📖 开始处理 HTML 文件: {html_path}")
    
    try:
        # 分离中英文内容
        print("\n" + "="*60)
        print("正在分离中英文内容...")
        print("="*60)
        en_chapters, zh_chapters = separate_en_zh_chapters(html_path)
        
        print(f"📊 提取到 {len(en_chapters)} 个英文章节")
        print(f"📊 提取到 {len(zh_chapters)} 个中文章节")
        
        # 打印前几个章节的标题
        print("\n英文章节预览:")
        for i, ch in enumerate(en_chapters[:3]):
            title_preview = ch['title'][:50] + "..." if len(ch['title']) > 50 else ch['title']
            content_preview = ch['content'][:80] + "..." if len(ch['content']) > 80 else ch['content']
            print(f"  章节 {i+1}: {title_preview}")
            print(f"    内容预览: {content_preview}")
        
        print("\n中文章节预览:")
        for i, ch in enumerate(zh_chapters[:3]):
            title_preview = ch['title'][:50] + "..." if len(ch['title']) > 50 else ch['title']
            content_preview = ch['content'][:80] + "..." if len(ch['content']) > 80 else ch['content']
            print(f"  章节 {i+1}: {title_preview}")
            print(f"    内容预览: {content_preview}")
        
        # 保存英文和中文章节
        save_chapters_json(en_chapters, output_en)
        save_chapters_json(zh_chapters, output_zh)
        
        print("\n" + "="*60)
        print("✅ 处理完成！")
        print("="*60)
        print(f"📁 英文内容已保存: {output_en}")
        print(f"📁 中文内容已保存: {output_zh}")
        
    except Exception as e:
        print(f"❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

