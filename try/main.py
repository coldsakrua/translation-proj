from utils.config_loader import ConfigLoader
from utils.logger import setup_logger
from utils.human import review_glossary
from utils.book_cut import split_epub_by_chapter
from utils.book_cut import split_chapter_into_chunks
from core.state_manager import StateManager
from core.action_executor import ActionExecutor
from core.learning_engine import LearningEngine
from core.base_agent import BaseAgent
from task import TranslationTask
from pathlib import Path

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
        # print(f"\n🚀 Resuming translation for Chunk {chunk_id}...")
        # final_result = handler.resume(reviewed_glossary, state_values)
        # quality = final_result["result"].get("quality_score", "N/A")
        # print(f"✅ Chunk {chunk_id} Finished. Score: {quality}")
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
        print(f"  📝 Translating Chunk {chunk_id}...")
        
        # 完整执行翻译流程，不中断
        state_values = handler.run(task["input"])
        
        quality = state_values.get("quality_score", "N/A")
        print(f"  ✅ Chunk {chunk_id} Finished. Score: {quality}")
        
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
    收集整个chapter所有chunk的术语表
    """
    import json
    import os
    all_glossaries = []
    
    for chunk_id in range(num_chunks):
        chunk_file = f"output/{book_id}/chapter_{chapter_id}/chunk_{chunk_id:03d}.json"
        if os.path.exists(chunk_file):
            with open(chunk_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'glossary' in data:
                    all_glossaries.extend(data['glossary'])
    
    # 去重：相同src的术语只保留一个（保留第一个出现的）
    seen_src = set()
    unique_glossaries = []
    for term in all_glossaries:
        src = term.get('src', '')
        if src and src not in seen_src:
            seen_src.add(src)
            unique_glossaries.append(term)
    
    return unique_glossaries

def update_chunks_with_reviewed_glossary(book_id, chapter_id, num_chunks, reviewed_glossary):
    """
    将人工审查后的术语表更新到所有chunk文件中
    
    Args:
        book_id: 书籍ID
        chapter_id: 章节ID
        num_chunks: chunk数量
        reviewed_glossary: 审查后的术语列表
    """
    import json
    import os
    
    # 创建术语字典，方便查找
    reviewed_dict = {term.get('src', ''): term for term in reviewed_glossary if term.get('src')}
    
    updated_count = 0
    for chunk_id in range(num_chunks):
        chunk_file = f"output/{book_id}/chapter_{chapter_id}/chunk_{chunk_id:03d}.json"
        if not os.path.exists(chunk_file):
            continue
        
        try:
            # 读取chunk文件
            with open(chunk_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
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
                
                # 保存更新后的文件
                with open(chunk_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                updated_count += 1
        except Exception as e:
            print(f"  ⚠️  更新 chunk_{chunk_id:03d}.json 失败: {e}")
    
    print(f"  ✅ 已更新 {updated_count} 个chunk文件中的术语表")

def run_book_translation(json_path, agent, book_id="AlexNet_Paper"):
    """从 JSON 文件读取章节并翻译（chapter级别人工审查）"""
    chapters = split_epub_by_chapter(json_path)

    for chapter_id, chap in enumerate(chapters):
        chapter_title = chap.get("title", f"Chapter {chapter_id}")
        print("\n" + "="*60)
        print(f"📖 Chapter {chapter_id}: {chapter_title}")
        print("="*60)
        
        content = chap.get("content", "")
        if not content:
            print(f"  ⚠️  Chapter {chapter_id} is empty, skipping...")
            continue
        
        # 如果内容超过一定长度，仍然需要分割
        chunks = split_chapter_into_chunks(content)
        print(f"  📊 Total chunks: {len(chunks)}")
        
        # ===== 阶段1: 自动翻译所有chunks =====
        print(f"\n  🔄 Phase 1: Auto-translating all chunks...")
        chunk_results = []
        for chunk_id, chunk_text in enumerate(chunks):
            task = {
                "input": {
                    "book_id": book_id,
                    "chapter_id": chapter_id,
                    "chunk_id": chunk_id,
                    "source_text": chunk_text,
                    "thread_id": f"ch{chapter_id}_ck{chunk_id}",
                }
            }
            result = agent.run_chunk_auto(task)
            chunk_results.append(result)
        
        # ===== 阶段2: 收集整个chapter的术语表并人工审查 =====
        print(f"\n  🛑 Phase 2: Human review for Chapter {chapter_id}...")
        chapter_glossary = collect_chapter_glossaries(book_id, chapter_id, len(chunks))
        
        if chapter_glossary:
            print(f"  📋 Found {len(chapter_glossary)} unique terms in this chapter")
            reviewed_glossary = review_glossary(chapter_glossary)
            print(f"  ✅ Reviewed glossary: {len(reviewed_glossary)} terms")
            
            # ===== 更新所有chunk文件中的术语表 =====
            print(f"\n  💾 Updating glossary in chunk files...")
            update_chunks_with_reviewed_glossary(book_id, chapter_id, len(chunks), reviewed_glossary)
        else:
            print(f"  ℹ️  No terms found in this chapter")
            reviewed_glossary = []
        
        print(f"\n  ✅ Chapter {chapter_id} completed!")
        print("-" * 60 + "\n")

def main():

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
    
    # 原来的 EPUB 路径（已注释）
    # path = "D:/hw/translation-proj/5Chapter_output/Artificial Intelligence_ A Modern Approach 4th Ed.epub"
    # run_book_translation(path, agent)
    
    # 新的 JSON 文件路径
    json_path = "D:/hw/translation-proj/data/3_en.json"
    run_book_translation(str(json_path), agent, book_id="YOLO")

if __name__ == "__main__":
    main()
