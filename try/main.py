from utils.config_loader import ConfigLoader
from utils.logger import setup_logger
from utils.human import review_glossary
from utils.book_cut import split_epub_by_chapter
from utils.book_cut import split_chapter_into_chunks
from utils.glossary_storage import load_reviewed_glossary
from utils.memory_storage import (
    get_previous_chapter_summaries,
    save_chapter_summary,
    get_chapter_translation_memory
)
from core.state_manager import StateManager
from core.action_executor import ActionExecutor
from core.learning_engine import LearningEngine
from core.base_agent import BaseAgent
from task import TranslationTask
from pathlib import Path
import json
import argparse
from datetime import datetime

class BaseAgent:
    def __init__(self, name, state_manager, executor, learner, logger, max_steps):
        self.name = name
        self.logger = logger
        self.max_steps = max_steps

    def run(self, task):
        """
        原有的逐chunk人工介入逻辑（已注释，改为chapter级别审查）
        """
        # # 初始化任务处理器
        # handler = TranslationTask(self.logger)
        # # --- 打印任务起始边界 ---
        # task_input = task.get("input", {})
        # chapter_id = task_input.get("chapter_id", "UNKNOWN")
        # chunk_id = task_input.get("chunk_id", "UNKNOWN")
        # print("\n" + "="*60)
        # print(f"📌 Task: Chapter {chapter_id} - Chunk {chunk_id}")
        # print("="*60)
        # # 1. 运行任务到中断点，获取当前的【状态数据字典】
        # # 注意：这里改名为 state_values，避免和 thread_id 配置混淆
        # state_values = handler.run(task["input"]) 
        # 
        # # 2. 提取自动生成的术语表
        # auto_glossary = handler.get_glossary(state_values)
        # 
        # # 3. —— 人工修正 ——
        # reviewed_glossary = review_glossary(auto_glossary)
        # 
        # # 4. 继续执行剩余流程
        # # 注意：必须匹配 resume(updated_glossary, state_dict) 的参数顺序
        # print(f"\nResuming translation for Chunk {chunk_id}...")
        # final_result = handler.resume(reviewed_glossary, state_values)
        # quality = final_result["result"].get("quality_score", "N/A")
        # print(f"√ Chunk {chunk_id} Finished. Score: {quality}")
        # print("-" * 60 + "\n") 
        # return final_result
        pass
    
    def run_chunk_auto(self, task):
        """
        自动翻译单个chunk，不中断（用于chapter级别审查模式）
        """
        handler = TranslationTask(self.logger)
        task_input = task.get("input", {})
        chapter_id = task_input.get("chapter_id", "UNKNOWN")
        chunk_id = task_input.get("chunk_id", "UNKNOWN")
        print(f"  Translating Chunk {chunk_id}...")
        
        # 完整执行翻译流程，不中断
        state_values = handler.run(task["input"])
        
        quality = state_values.get("quality_score", "N/A")
        print(f"  √ Chunk {chunk_id} Finished. Score: {quality}")
        
        return state_values
    
# def run_book_translation(epub_path, agent):
#     chapters = split_epub_by_chapter(epub_path)
# 
#     for chapter_id, chap in enumerate(chapters):
#         chunks = split_chapter_into_chunks(chap["content"])
# 
#         for chunk_id, chunk_text in enumerate(chunks):
#             task = {
#                 "input": {
#                     "book_id": "AIMA_4th",
#                     "chapter_id": chapter_id,
#                     "chunk_id": chunk_id,
#                     "source_text": chunk_text,
#                     "thread_id": f"ch{chapter_id}_ck{chunk_id}",
#                 }
#             }
# 
#             agent.run(task)

def collect_chapter_glossaries(book_id, chapter_id, num_chunks):
    """
    收集整个chapter所有chunk的术语表和原文
    """
    import json
    import os
    all_glossaries = []
    chapter_source_text = []  # 收集所有原文，用于显示上下文
    
    for chunk_id in range(num_chunks):
        chunk_file = f"output/{book_id}/chapter_{chapter_id}/chunk_{chunk_id:03d}.json"
        if os.path.exists(chunk_file):
            with open(chunk_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'glossary' in data:
                    all_glossaries.extend(data['glossary'])
                if 'source_text' in data:
                    chapter_source_text.append(data['source_text'])
    
    # 去重：相同src的术语只保留一个（保留第一个出现的）
    seen_src = set()
    unique_glossaries = []
    for term in all_glossaries:
        src = term.get('src', '')
        if src and src not in seen_src:
            seen_src.add(src)
            unique_glossaries.append(term)
    
    # 合并所有原文
    full_source_text = "\n\n".join(chapter_source_text)
    
    return unique_glossaries, full_source_text

def update_chunks_with_reviewed_glossary(book_id, chapter_id, num_chunks, reviewed_glossary):
    """
    将人工审查后的术语表更新到所有chunk文件中，并更新译文中的术语翻译
    
    Args:
        book_id: 书籍ID
        chapter_id: 章节ID
        num_chunks: chunk数量
        reviewed_glossary: 审查后的术语列表
    """
    import json
    import os
    import re
    
    # 创建术语字典，方便查找
    reviewed_dict = {term.get('src', ''): term for term in reviewed_glossary if term.get('src')}
    
    # 找出所有被人工修改的术语（需要更新译文的）
    translation_updates = {}  # {original_trans: new_trans}
    for term in reviewed_glossary:
        if term.get('human_modified', False) and 'original_suggested_trans' in term:
            original_trans = term['original_suggested_trans']
            new_trans = term.get('suggested_trans', '')
            if original_trans and new_trans and original_trans != new_trans:
                translation_updates[original_trans] = new_trans
    
    updated_count = 0
    translation_updated_count = 0
    
    for chunk_id in range(num_chunks):
        chunk_file = f"output/{book_id}/chapter_{chapter_id}/chunk_{chunk_id:03d}.json"
        if not os.path.exists(chunk_file):
            continue
        
        try:
            # 读取chunk文件
            with open(chunk_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            translation_updated = False
            
            # 更新术语表
            if 'glossary' in data and isinstance(data['glossary'], list):
                updated_glossary = []
                for term in data['glossary']:
                    src = term.get('src', '')
                    if src in reviewed_dict:
                        # 使用审查后的术语信息
                        updated_term = reviewed_dict[src].copy()
                        # 保留原有的一些字段（如果审查后的术语没有）
                        for key in ['context_meaning']:
                            if key not in updated_term and key in term:
                                updated_term[key] = term[key]
                        updated_glossary.append(updated_term)
                    else:
                        # 保留原有术语
                        updated_glossary.append(term)
                
                data['glossary'] = updated_glossary
                
                # 添加人工审查标记
                data['human_reviewed'] = True
                data['reviewed_glossary_count'] = len([t for t in updated_glossary if t.get('human_reviewed', False)])
                
            # 更新译文中的术语翻译
            if 'translation' in data and data['translation'] and translation_updates:
                translation = data['translation']
                # 按长度降序排序，优先替换较长的术语，避免短术语被长术语包含
                sorted_updates = sorted(translation_updates.items(), key=lambda x: len(x[0]), reverse=True)
                
                for original_trans, new_trans in sorted_updates:
                    # 直接替换，因为术语通常是完整的词或短语
                    # 如果原文中存在该术语，则替换
                    if original_trans in translation:
                        # 使用字符串替换（简单直接）
                        translation = translation.replace(original_trans, new_trans)
                        translation_updated = True
                
                data['translation'] = translation
                
                # 添加译文更新标记
                if translation_updated:
                    data['translation_updated_by_glossary'] = True
                    data['translation_updated_at'] = datetime.now().isoformat()
            
                # 保存更新后的文件
                with open(chunk_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                updated_count += 1
            if translation_updated:
                translation_updated_count += 1
                
                # 同时更新翻译记忆库
                try:
                    from utils.memory_storage import load_translation_memory, save_translation_memory
                    memory_key = f"{book_id}_ch{chapter_id}_ck{chunk_id}"
                    memory = load_translation_memory(book_id)
                    if memory_key in memory:
                        memory[memory_key]['translation'] = data['translation']
                        memory[memory_key]['updated_at'] = datetime.now().isoformat()
                        # 保存更新后的记忆库
                        memory_file = f"output/{book_id}/translation_memory.json"
                        with open(memory_file, 'w', encoding='utf-8') as f:
                            json.dump(memory, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    print(f"  [WARNING] 更新翻译记忆库失败: {e}")
                    
        except Exception as e:
            print(f"  [WARNING] 更新 chunk_{chunk_id:03d}.json 失败: {e}")
    
    print(f"  √ 已更新 {updated_count} 个chunk文件中的术语表")
    if translation_updated_count > 0:
        print(f"  √ 已更新 {translation_updated_count} 个chunk文件中的译文（根据术语审查结果）")

def generate_chapter_summary(book_id, chapter_id, chunks_data, enable_human_review=True):
    """
    生成章节摘要
    
    Args:
        book_id: 书籍ID
        chapter_id: 章节ID
        chunks_data: chunk数据列表，每个包含source_text和translation
        enable_human_review: 是否启用人工审查模式（用于控制速率限制）
    """
    try:
        from core.get_llm import llm
        from core.nodes import _rate_limiter
        
        # 收集所有原文和译文
        source_texts = [chunk.get('source_text', '') for chunk in chunks_data]
        translations = [chunk.get('translation', '') for chunk in chunks_data]
        
        combined_source = "\n\n".join(source_texts[:5])  # 只取前5个chunk
        combined_translation = "\n\n".join(translations[:5])
        
        prompt = f"""
请为以下章节生成摘要和关键点。

【原文（前5个chunk）】
{combined_source[:2000]}

【译文（前5个chunk）】
{combined_translation[:2000]}

请生成：
1. 章节摘要（100-200字，中文）
2. 关键点列表（3-5个要点）

请严格按照以下JSON格式输出：
{{
    "summary": "章节摘要",
    "key_points": ["要点1", "要点2", "要点3"]
}}
"""
        try:
            from pydantic import BaseModel, Field
            class ChapterSummary(BaseModel):
                summary: str = Field(description="章节摘要")
                key_points: list = Field(description="关键点列表")
            
            # 速率限制检查（如果禁用了人工审查）
            _rate_limiter.wait_if_needed(enable_human_review)
            structured_llm = llm.with_structured_output(ChapterSummary)
            result = structured_llm.invoke(prompt)
            summary_data = result.model_dump()
            
            # 保存摘要
            save_chapter_summary(
                book_id=book_id,
                chapter_id=chapter_id,
                summary=summary_data['summary'],
                key_points=summary_data['key_points']
            )
            print(f"  √ 章节摘要已生成并保存")
            return summary_data
        except Exception as e:
            print(f"  [WARNING] 生成章节摘要失败: {e}")
            return None
    except Exception as e:
        print(f"  [WARNING] 生成章节摘要时出错: {e}")
        return None


def review_chapter_translation(book_id, chapter_id, num_chunks):
    """
    人工审查章节翻译质量
    
    Args:
        book_id: 书籍ID
        chapter_id: 章节ID
        num_chunks: chunk数量
    
    Returns:
        审查结果字典，包含 accepted 和 feedback 字段
    """
    import json
    import os
    
    print("\n" + "="*60)
    print(f"章节 {chapter_id} 翻译质量审查")
    print("="*60)
    
    # 收集所有chunk的翻译（过滤掉source_text为空的）
    translations = []
    for chunk_id in range(num_chunks):
        chunk_file = f"output/{book_id}/chapter_{chapter_id}/chunk_{chunk_id:03d}.json"
        if os.path.exists(chunk_file):
            with open(chunk_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                source_text = data.get('source_text', '').strip()
                # 只添加source_text不为空的chunk
                if source_text:
                    translations.append({
                        "chunk_id": chunk_id,
                        "source_text": source_text,
                        "translation": data.get('translation', ''),
                        "quality_score": data.get('quality_score', 0)
                    })
    
    if not translations:
        print("  [WARNING] 未找到有效的翻译结果（所有chunk的source_text都为空）")
        return {"accepted": False, "feedback": "未找到有效的翻译结果"}
    
    # 显示翻译统计（只统计有效的translations）
    scores = [t['quality_score'] for t in translations if t.get('quality_score')]
    avg_score = sum(scores) / len(scores) if scores else 0
    print(f"\n  翻译统计（已排除空文本）:")
    print(f"     - 有效chunk数: {len(translations)}")
    print(f"     - 平均质量分: {avg_score:.1f}/10")
    
    # 保存质量评分到单独文件
    quality_scores_file = f"output/{book_id}/chapter_{chapter_id}/quality_scores.json"
    try:
        os.makedirs(os.path.dirname(quality_scores_file), exist_ok=True)
        quality_data = {
            "book_id": book_id,
            "chapter_id": chapter_id,
            "reviewed_at": datetime.now().isoformat(),
            "statistics": {
                "total_chunks": len(translations),
                "average_score": round(avg_score, 2),
                "min_score": round(min(scores), 2) if scores else None,
                "max_score": round(max(scores), 2) if scores else None,
                "scores_count": len(scores),
                "note": "已排除source_text为空的chunk"
            },
            "chunk_scores": [
                {
                    "chunk_id": t['chunk_id'],
                    "quality_score": t['quality_score'],
                    "source_preview": t['source_text'][:100] + "..." if len(t['source_text']) > 100 else t['source_text'],
                    "translation_preview": t['translation'][:100] + "..." if len(t['translation']) > 100 else t['translation']
                }
                for t in translations
            ]
        }
        with open(quality_scores_file, 'w', encoding='utf-8') as f:
            json.dump(quality_data, f, ensure_ascii=False, indent=2)
        print(f"     - 质量评分已保存到: {quality_scores_file}")
    except Exception as e:
        print(f"     [WARNING] 保存质量评分失败: {e}")
    
    # 显示前3个chunk的翻译示例
    print(f"\n  翻译示例（前3个chunk）:")
    for i, t in enumerate(translations[:3], 1):
        print(f"\n  [示例 {i}] Chunk {t['chunk_id']}")
        print(f"  原文: {t['source_text'][:150]}...")
        print(f"  译文: {t['translation'][:150]}...")
        print(f"  质量分: {t['quality_score']}/10")
    
    # 询问是否接受（带超时）
    print(f"\n" + "-"*60)
    from utils.input_with_timeout import input_with_timeout
    
    # 第一次询问（3分钟超时，默认接受）
    action = input_with_timeout(
        "是否接受本章节翻译？ [y=接受 | n=不接受 | s=跳过] (3分钟超时自动接受) > ",
        timeout=180.0,  # 3分钟 = 180秒
        default="y"
        ).strip().lower()
        
    if action == "y" or action == "":
        print("  √ 已接受本章节翻译")
        return {"accepted": True, "feedback": ""}
    elif action == "n":
        # 如果不接受，询问修改意见（3分钟超时）
        feedback = input_with_timeout(
            "  请输入修改意见（可直接回车跳过，3分钟超时自动跳过）: ",
            timeout=180.0,  # 3分钟 = 180秒
            default=""
        ).strip()
        return {"accepted": False, "feedback": feedback or "需要修改"}
    elif action == "s":
        print("  跳过审查")
        return {"accepted": True, "feedback": "跳过审查"}
    else:
        print("  [WARNING] 无效操作，默认接受")
        return {"accepted": True, "feedback": ""}


def load_global_glossary(book_id, current_chapter_id):
    """
    加载全局术语表（之前章节的已审查术语）
    
    Args:
        book_id: 书籍ID
        current_chapter_id: 当前章节ID
    
    Returns:
        全局术语表字典
    """
    try:
        # 加载已审查的术语库
        reviewed_glossary = load_reviewed_glossary()
        
        # 过滤出当前书籍的术语（如果有book_id标记的话）
        # 或者直接返回所有已审查的术语
        global_glossary = {}
        for term_src, term_info in reviewed_glossary.items():
            if isinstance(term_info, dict):
                global_glossary[term_src] = term_info
        
        if global_glossary:
            print(f"  加载了 {len(global_glossary)} 个全局术语（来自之前章节）")
        else:
            print(f"  暂无全局术语表")
        
        return global_glossary
    except Exception as e:
        print(f"  [WARNING] 加载全局术语表失败: {e}")
        return {}


def run_book_translation(json_path, agent, book_id="AlexNet_Paper", enable_human_review=True, use_rag=True):
    """
    从 JSON 文件读取章节并翻译（chapter级别人工审查）
    
    Args:
        json_path: JSON文件路径
        agent: 翻译代理
        book_id: 书籍ID
        enable_human_review: 是否启用人工审查（默认True）
        use_rag: 是否使用 RAG 检索（默认True）
    """
    # 根据配置修改book_id后缀
    # 如果没有人工介入，修改book_id为book_id_nohuman
    if not enable_human_review:
        book_id = f"{book_id}_nohuman"
    # 如果没有使用RAG，在book_id后加上_norag
    if not use_rag:
        book_id = f"{book_id}_norag"
    
    
    chapters = split_epub_by_chapter(json_path)

    for chapter_id, chap in enumerate(chapters):
        chapter_title = chap.get("title", f"Chapter {chapter_id}")
        print("\n" + "="*60)
        print(f"Chapter {chapter_id}: {chapter_title}")
        print("="*60)
        
        content = chap.get("content", "")
        if not content:
            print(f"  [WARNING] Chapter {chapter_id} is empty, skipping...")
            continue
        
        # ===== 加载全局术语表和章节上下文 =====
        print(f"\n  Loading global context...")
        global_glossary = load_global_glossary(book_id, chapter_id)
        
        # 加载之前章节的摘要
        try:
            prev_summaries = get_previous_chapter_summaries(book_id, chapter_id)
            if prev_summaries:
                print(f"  加载了 {len(prev_summaries)} 个之前章节的摘要")
        except Exception as e:
            print(f"  [WARNING] 加载章节摘要失败: {e}")
        
        # 如果内容超过一定长度，仍然需要分割
        chunks = split_chapter_into_chunks(content)
        print(f"  Total chunks: {len(chunks)}")
        
        # ===== 阶段1: 自动翻译所有chunks =====
        print(f"\n  Phase 1: Auto-translating all chunks...")
        chunk_results = []
        chunks_data = []  # 用于生成摘要
        
        for chunk_id, chunk_text in enumerate(chunks):
            task = {
                "input": {
                    "book_id": book_id,
                    "chapter_id": chapter_id,
                    "chunk_id": chunk_id,
                    "source_text": chunk_text,
                    "thread_id": f"ch{chapter_id}_ck{chunk_id}",
                    # 传递全局术语表
                    "global_glossary": global_glossary,
                    # 传递人工审查模式标志（用于控制速率限制）
                    "enable_human_review": enable_human_review,
                    # 传递 RAG 使用标志
                    "use_rag": use_rag,
                }
            }
            result = agent.run_chunk_auto(task)
            chunk_results.append(result)
            
            # 收集chunk数据用于生成摘要
            if isinstance(result, dict):
                chunks_data.append({
                    "source_text": result.get("source_text", chunk_text),
                    "translation": result.get("combined_translation", "")
                })
        
        # ===== 阶段2: 收集整个chapter的术语表并人工审查 =====
        if enable_human_review:
            print(f"\n  Phase 2: Human review for Chapter {chapter_id}...")
        else:
            print(f"\n  Phase 2: Auto-accepting glossary for Chapter {chapter_id}...")
        
        chapter_glossary, chapter_source_text = collect_chapter_glossaries(book_id, chapter_id, len(chunks))
        
        if chapter_glossary:
            print(f"  Found {len(chapter_glossary)} unique terms in this chapter")
            if enable_human_review:
                reviewed_glossary = review_glossary(chapter_glossary, chapter_source_text)
            else:
                # 自动接受所有术语
                reviewed_glossary = chapter_glossary
                for term in reviewed_glossary:
                    term["human_reviewed"] = True
                    term["human_modified"] = False
                print(f"  √ Auto-accepted {len(reviewed_glossary)} terms (人工审查已禁用)")
            
            print(f"  √ Reviewed glossary: {len(reviewed_glossary)} terms")
            
            # ===== 更新所有chunk文件中的术语表 =====
            print(f"\n  Updating glossary in chunk files...")
            update_chunks_with_reviewed_glossary(book_id, chapter_id, len(chunks), reviewed_glossary)
        else:
            print(f"  No terms found in this chapter")
            reviewed_glossary = []
        
        # ===== 阶段3: 生成章节摘要 =====
        print(f"\n  Phase 3: Generating chapter summary...")
        if chunks_data:
            generate_chapter_summary(book_id, chapter_id, chunks_data, enable_human_review)
        
        # ===== 阶段4: 章节翻译质量人工审查（带重新翻译循环） =====
        if enable_human_review:
            max_retry_count = 3  # 最大重试次数
            retry_count = 0
            chapter_review_result = None
            
            while retry_count <= max_retry_count:
                print(f"\n  Phase 4: Chapter translation quality review (尝试 {retry_count + 1}/{max_retry_count + 1})...")
                chapter_review_result = review_chapter_translation(book_id, chapter_id, len(chunks))
                
                if chapter_review_result and chapter_review_result.get('accepted', False):
                    print(f"  √ 章节翻译已通过审查")
                    break
                else:
                    feedback = chapter_review_result.get('feedback', '需要修改') if chapter_review_result else '需要修改'
                    print(f"  [WARNING] 章节翻译未通过审查")
                    print(f"  修改意见: {feedback}")
                    
                    if retry_count < max_retry_count:
                        print(f"\n  >>> 开始重新翻译（根据修改意见）...")
                        
                        # 重新翻译所有chunks（使用修改意见）
                        chunk_results = []
                        chunks_data = []
                        
                        for chunk_id, chunk_text in enumerate(chunks):
                            task = {
                                "input": {
                                    "book_id": book_id,
                                    "chapter_id": chapter_id,
                                    "chunk_id": chunk_id,
                                    "source_text": chunk_text,
                                    "thread_id": f"ch{chapter_id}_ck{chunk_id}_retry{retry_count + 1}",
                                    "global_glossary": global_glossary,
                                    "critique": feedback,  # 传递修改意见到critique字段
                                    "is_retry": True,  # 标记为重新翻译
                                    # 传递人工审查模式标志（用于控制速率限制）
                                    "enable_human_review": enable_human_review,
                                    # 传递 RAG 使用标志
                                    "use_rag": use_rag,
                                }
                            }
                            result = agent.run_chunk_auto(task)
                            chunk_results.append(result)
                            
                            # 收集chunk数据用于生成摘要
                            if isinstance(result, dict):
                                chunks_data.append({
                                    "source_text": result.get("source_text", chunk_text),
                                    "translation": result.get("combined_translation", "")
                                })
                        
                        print(f"  √ 重新翻译完成，准备再次审查...")
                        retry_count += 1
                    else:
                        print(f"  [WARNING] 已达到最大重试次数（{max_retry_count}次），停止重试")
                        break
        else:
            # 自动接受章节翻译
            print(f"\n  Phase 4: Auto-accepting chapter translation (人工审查已禁用)...")
            print(f"  √ 章节翻译已自动接受")
        
        print(f"\n  √ Chapter {chapter_id} completed!")
        print("-" * 60 + "\n")

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="论文翻译工具")
    parser.add_argument(
        "--no-human-review",
        action="store_true",
        help="禁用人工审查（自动接受所有术语和翻译）"
    )
    parser.add_argument(
        "--paper-id",
        type=str,
        default="vgg",
        help="论文ID（默认: vgg）"
    )
    parser.add_argument(
        "--json-path",
        type=str,
        default=None,
        help="JSON文件路径（如果不指定，将使用 --paper-id 自动构建路径）"
    )
    parser.add_argument(
        "--no-rag",
        action="store_true",
        help="禁用 RAG 检索，直接翻译（不使用翻译记忆检索）"
    )
    
    args = parser.parse_args()
    
    # 确定是否启用人工审查
    enable_human_review = not args.no_human_review
    
    # 确定是否使用 RAG 检索
    use_rag = not args.no_rag
    
    if enable_human_review:
        print("="*60)
        print("人工审查模式：已启用")
        print("="*60)
    else:
        print("="*60)
        print("自动模式：人工审查已禁用，将自动接受所有术语和翻译")
        print("="*60)
    
    if use_rag:
        print("RAG 检索：已启用")
    else:
        print("RAG 检索：已禁用（直接翻译模式）")
    print("="*60)
    
    config = ConfigLoader("agents/config.yml")
    config.validate()

    logger = setup_logger(
        "Agent",
        config.get("logging")["log_file"]
    )

    state = StateManager(config.get("agent")["memory_size"])
    executor = ActionExecutor(**config.get("execution"))
    learner = LearningEngine()

    agent = BaseAgent(
        name=config.get("agent")["name"],
        state_manager=state,
        executor=executor,
        learner=learner,
        logger=logger,
        max_steps=config.get("agent")["max_steps"]
    )
    
    # 确定JSON文件路径
    if args.json_path:
        json_path = args.json_path
    else:
        json_path = f"D:/hw/translation-proj/data/{args.paper_id}_en.json"
    
    print(f"\n使用文件: {json_path}")
    print(f"书籍ID: {args.paper_id}\n")
    
    run_book_translation(
        str(json_path), 
        agent, 
        book_id=args.paper_id,
        enable_human_review=enable_human_review,
        use_rag=use_rag
    )

if __name__ == "__main__":
    main()
