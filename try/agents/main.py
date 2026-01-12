from utils.config_loader import ConfigLoader
from utils.logger import setup_logger
from utils.human import review_glossary
from utils.book_cut import split_epub_by_chapter
from utils.book_cut import split_chapter_into_chunks
from core.state_manager import StateManager
from core.action_executor import ActionExecutor
from core.learning_engine import LearningEngine
from core.base_agent import BaseAgent
from .task import TranslationTask

class BaseAgent:
    def __init__(self, name, state_manager, executor, learner, logger, max_steps):
        self.name = name
        self.logger = logger
        self.max_steps = max_steps

    def run(self, task):
        # 初始化任务处理器
        handler = TranslationTask(self.logger)
        # --- 打印任务起始边界 ---
        task_input = task.get("input", {})
        chapter_id = task_input.get("chapter_id", "UNKNOWN")
        chunk_id = task_input.get("chunk_id", "UNKNOWN")
        print("\n" + "="*60)
        print(f"Task: Chapter {chapter_id} - Chunk {chunk_id}")
        print("="*60)
        # 1. 运行任务到中断点，获取当前的【状态数据字典】
        # 注意：这里改名为 state_values，避免和 thread_id 配置混淆
        state_values = handler.run(task["input"]) 
        
        # 2. 提取自动生成的术语表
        auto_glossary = handler.get_glossary(state_values)
        
        # 3. —— 人工修正 ——
        reviewed_glossary = review_glossary(auto_glossary)
        
        # 4. 继续执行剩余流程
        # 注意：必须匹配 resume(updated_glossary, state_dict) 的参数顺序
        print(f"\nResuming translation for Chunk {chunk_id}...")
        final_result = handler.resume(reviewed_glossary, state_values)
        quality = final_result["result"].get("quality_score", "N/A")
        print(f"√ Chunk {chunk_id} Finished. Score: {quality}")
        print("-" * 60 + "\n") 
        return final_result
    
def run_book_translation(epub_path, agent):
    chapters = split_epub_by_chapter(epub_path)

    for chapter_id, chap in enumerate(chapters):
        chunks = split_chapter_into_chunks(chap["content"])

        for chunk_id, chunk_text in enumerate(chunks):
            task = {
                "input": {
                    "book_id": "AIMA_4th",
                    "chapter_id": chapter_id,
                    "chunk_id": chunk_id,
                    "source_text": chunk_text,
                    "thread_id": f"ch{chapter_id}_ck{chunk_id}",
                }
            }

            agent.run(task)

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
    
    path = "F:/PKU/homework/LLM/T-Ragx-main/5Chapter_output/Artificial Intelligence_ A Modern Approach 4th Ed.epub"
    run_book_translation(path, agent)

if __name__ == "__main__":
    main()
