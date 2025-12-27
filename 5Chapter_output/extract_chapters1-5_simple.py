"""
前五章提取脚本（简化版，仅提取功能，无NLP依赖）
"""
import re
import json
import sys
import io

# 设置标准输出编码为UTF-8，解决Windows控制台中文显示问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# -------------------------- 核心配置 --------------------------
INPUT_TXT = "./AIBookEnglish.txt"
TARGET_CHAPTERS = [1, 2, 3, 4, 5]
OUTPUT_JSON = "chapters1-5_extracted.json"

# -------------------------- 前五章精确章节名映射 --------------------------
CHAPTER_TITLES = {
    1: "INTRODUCTION",
    2: "INTELLIGENT AGENTS",
    3: "SOLVING PROBLEMS BY SEARCHING",
    4: "SEARCH IN COMPLEX ENVIRONMENTS",
    5: "CONSTRAINT SATISFACTION PROBLEMS"
}

# -------------------------- 文本预处理辅助函数 --------------------------
def clean_text(text):
    """清理多余空行，保留段落分隔"""
    # 合并3个及以上空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

# -------------------------- 核心提取函数 --------------------------
def extract_chapters(txt_path, target_chapters):
    """
    提取指定章节的内容
    
    Args:
        txt_path: TXT文件路径
        target_chapters: 要提取的章节列表，如 [1, 2, 3, 4, 5]
    
    Returns:
        dict: 包含每个章节标题和内容的字典
    """
    print(f"正在读取文件：{txt_path}")
    
    # 读取文件
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            full_text = f.read()
    except UnicodeDecodeError:
        with open(txt_path, 'r', encoding='gbk', errors='ignore') as f:
            full_text = f.read()
    
    print(f"✅ 文件读取成功，总字符数：{len(full_text)}")
    
    # 跳过前置内容，从CHAPTER 1开始
    chapter1_match = re.search(r'(?i)^CHAPTER\s+1', full_text, re.MULTILINE)
    if chapter1_match:
        full_text = full_text[chapter1_match.start():]
        print("✅ 已跳过前置内容，从CHAPTER 1开始")
    else:
        raise ValueError("❌ 未找到CHAPTER 1，检查文档格式是否正确")
    
    chapters_data = {}
    
    for chap_num in target_chapters:
        chap_title = f"Chapter {chap_num}"
        chap_content = ""
        
        print(f"\n正在提取第{chap_num}章...")
        
        # 构建匹配模式
        # 模式1: CHAPTER X + 标题（允许空行）
        # 匹配从 "CHAPTER X" 开始，到下一章或文档结束
        # 使用贪婪匹配确保捕获全部内容
        pattern = rf'''
            (?i)                    # 忽略大小写
            ^\s*CHAPTER\s+{chap_num}\s*$   # 匹配 "CHAPTER X"（允许前后空白）
            \s+                          # 章节号后任意空行
            ^\s*([^\n]+)\s*$           # 匹配标题
            \s+                          # 标题后任意空行
            ([\s\S]*)                # 贪婪捕获所有正文（去掉?使其贪婪）
            (?=                      # 终止条件：下一章或文档末尾
                ^\s*CHAPTER\s+{chap_num+1}\b
                |$
            )
        '''
        
        match = re.search(pattern, full_text, re.MULTILINE | re.DOTALL | re.VERBOSE)
        
        if match:
            # 提取标题
            matched_title = match.group(1).strip()
            
            # 标题校验
            expected_title = CHAPTER_TITLES.get(chap_num, "").upper()
            if expected_title and matched_title.upper() != expected_title:
                print(f"  ⚠️  检测到标题：{matched_title}")
                print(f"  ✅ 使用标准标题：{expected_title}")
                chap_title = f"Chapter {chap_num}: {expected_title}"
            else:
                chap_title = f"Chapter {chap_num}: {matched_title}" if matched_title else f"Chapter {chap_num}"
            
            # 提取内容
            chap_content = match.group(2).strip()
            
            # 清理内容
            chap_content = clean_text(chap_content)
            
            valid_chars = re.sub(r'[\s\t]', '', chap_content)
            valid_char_count = len(valid_chars)
            
            print(f"  ✅ 提取成功！")
            print(f"  标题：{chap_title}")
            print(f"  内容长度：{len(chap_content)}字符（有效：{valid_char_count}）")
            print(f"  前500字符预览：{chap_content[:500]}...")
            
        else:
            # 兜底截取
            print(f"  ⚠️  正则匹配失败，尝试兜底截取...")
            current_chap_mark = re.search(rf'(?i)^CHAPTER\s+{chap_num}', full_text, re.MULTILINE)
            next_chap_mark = re.search(rf'(?i)^CHAPTER\s+{chap_num+1}', full_text, re.MULTILINE)
            
            if current_chap_mark:
                start_pos = current_chap_mark.end()
                end_pos = next_chap_mark.start() if next_chap_mark else len(full_text)
                chap_content = full_text[start_pos:end_pos].strip()
                chap_content = clean_text(chap_content)
                chap_title = f"Chapter {chap_num}: {CHAPTER_TITLES.get(chap_num, f'Chapter {chap_num}')}"
                
                valid_chars = re.sub(r'[\s\t]', '', chap_content)
                valid_char_count = len(valid_chars)
                
                print(f"  ✅ 兜底提取成功！")
                print(f"  标题：{chap_title}")
                print(f"  内容长度：{len(chap_content)}字符（有效：{valid_char_count}）")
            else:
                print(f"  ❌ 章节{chap_num}提取失败！")
                continue
        
        # 保存数据
        chapters_data[chap_num] = {
            "title": chap_title,
            "content": chap_content,
            "char_count": len(chap_content),
            "valid_char_count": valid_char_count if 'valid_char_count' in locals() else 0
        }
    
    # 校验结果
    missing_chaps = [chap for chap in target_chapters if chap not in chapters_data]
    if missing_chaps:
        print(f"\n❌ 以下章节未提取到：{missing_chaps}")
    else:
        print(f"\n✅ 全部{len(target_chapters)}章提取成功！")
    
    return chapters_data

# -------------------------- 主函数 --------------------------
def main():
    print("="*80)
    print("《AI: A Modern Approach》前五章提取工具")
    print("="*80)
    
    # 提取章节
    chapters_data = extract_chapters(INPUT_TXT, TARGET_CHAPTERS)
    
    # 保存为JSON
    output = {
        "book_info": "Artificial Intelligence: A Modern Approach (4th Ed) - Chapters 1-5",
        "extracted_chapters": len(chapters_data),
        "chapters": chapters_data
    }
    
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 结果已保存至：{OUTPUT_JSON}")
    
    # 统计信息
    print("\n" + "="*80)
    print("提取统计：")
    print("="*80)
    total_chars = 0
    total_valid_chars = 0
    for chap_num, data in chapters_data.items():
        print(f"  章节{chap_num}：{data['title']}")
        print(f"    总字符数：{data['char_count']}")
        print(f"    有效字符数：{data['valid_char_count']}")
        total_chars += data['char_count']
        total_valid_chars += data['valid_char_count']
    
    print(f"\n  总计：{total_chars}字符（有效：{total_valid_chars}）")
    print("="*80)

if __name__ == "__main__":
    main()
