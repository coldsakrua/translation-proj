from core.graph import build_translation_agent
from core.nodes import TranslationState
class TranslationTask:
    def __init__(self, logger):
        self.logger = logger
        # 建议这里确保 build_translation_agent() 返回的 app 已经 compile 并设置了 checkpointer
        self.app = build_translation_agent()
        self.thread_id = None  # 这里的 thread_id 存储的是 LangGraph 的 config dict

    def run(self, input_data: dict):
        """
        完整执行翻译流程，不中断（用于 chapter 级别审查模式）
        """
        # 构造正确的 LangGraph config 字典
        t_id = str(input_data.get("thread_id", "default"))
        self.thread_id = {"configurable": {"thread_id": t_id}}

        # 完整执行工作流，不中断
        for event in self.app.stream(input_data, self.thread_id):
            # 打印正在执行的节点，方便调试
            for node_name in event.keys():
                print(f"   [Flow] Reached Node: {node_name}")

        # 获取最终状态快照
        state_snapshot = self.app.get_state(self.thread_id)
        self.logger.info(f"Translation completed for thread {t_id}")
        
        return state_snapshot.values  # 返回 dict 类型的数据

    def get_glossary(self, state_dict=None):
        """
        获取术语表。如果没传 state_dict，则从 checkpoint 现场拉取。
        """
        if state_dict is None:
            if not self.thread_id:
                raise ValueError("Thread ID not initialized. Run the task first.")
            state_snapshot = self.app.get_state(self.thread_id)
            state_dict = state_snapshot.values
            
        return state_dict.get("glossary", [])

    def resume(self, updated_glossary: list, state_dict: dict):
        """
        人工审查完成后恢复运行。
        """
        # 1. 关键修改：手动更新 Checkpoint 中的状态
        # 这样 LangGraph 就知道 'glossary' 已经被人工改过了
        self.app.update_state(
            self.thread_id, 
            {"glossary": updated_glossary}, 
            as_node="search_terms" # 伪装成是从 search_terms 节点更新的
        )

        # 2. 关键修改：传入 None 继续执行
        # 传入 None 会让 Graph 从 interrupt 的地方（即 translate 之前）直接向下走
        print(f"   >>> Continuing from checkpoint...")
        
        for event in self.app.stream(None, self.thread_id):
            # 打印正在执行的节点，方便调试
            for node_name in event.keys():
                print(f"   [Flow] Reached Node: {node_name}")

        # 3. 获取最终执行结果
        final_snapshot = self.app.get_state(self.thread_id)
        return {
            "status": "FINISHED",
            "result": final_snapshot.values
        }
    def assemble_chapter(self, book_id, chapter_id):
        """
        将所有保存的 chunk json 文件合并为一个 Markdown 或 Text
        """
        import glob
        import json
        path = f"output/{book_id}/chapter_{chapter_id}/chunk_*.json"
        files = sorted(glob.glob(path))
        
        full_translation = []
        for f in files:
            with open(f, 'r', encoding='utf-8') as reader:
                data = json.load(reader)
                full_translation.append(data['translation'])
        
        # 保存最终章节结果
        final_path = f"output/{book_id}/chapter_{chapter_id}_final.md"
        with open(final_path, 'w', encoding='utf-8') as f:
            f.write("\n\n".join(full_translation))
        
        return final_path