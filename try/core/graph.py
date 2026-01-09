from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from .nodes import *

def build_translation_agent():
    # ============================================
    # 3. 构建 Graph (Workflow Definition)
    # ============================================

    workflow = StateGraph(TranslationState)

    # 添加节点
    workflow.add_node("analyze_style", node_analyze_style)
    workflow.add_node("extract_terms", node_extract_terms)
    workflow.add_node("search_terms", node_search_and_consolidate)
    workflow.add_node("translate", node_translate_fusion)
    workflow.add_node("evaluate", node_tear_evaluation)
    workflow.add_node("persistence", node_persistence)

    # 构建流程连线
    workflow.add_edge(START, "analyze_style")
    workflow.add_edge("analyze_style", "extract_terms")
    workflow.add_edge("extract_terms", "search_terms")

    # --- 人机协作点 1: 术语确认 ---
    # 在 search_terms 结束后，我们希望暂停，让人类检查 glossary
    workflow.add_edge("search_terms", "translate")

    workflow.add_edge("translate", "evaluate")

    # --- 循环逻辑 (Router) ---
    # def quality_gate(state: TranslationState):
    #     # 限制最大迭代次数防止死循环
    #     if state["revision_count"] > 3:
    #         print("   >>> Max iterations reached. Force stop.")
    #         return "persistence"
        
    #     if state["quality_score"] >= 7:
    #         print("   >>> Quality verified. Finishing.")
    #         return "persistence"
    #     else:
    #         print("   >>> Quality insufficient. Refining...")
    #         return "translate" # 带着 critique 回到翻译节点
    def quality_gate(state: TranslationState):
    # 限制最大迭代次数防止死循环
    # 错误写法：state["revision_count"]
    # 正确写法：state.revision_count (因为你是 Pydantic 模型)
    
        if state.revision_count > 3:
            print("   >>> [Gate] Max iterations reached. Force stop.")
            return "persistence"
        
        # 同样修改质量分的判定
        if state.quality_score is not None and state.quality_score >= 7:
            print(f"   >>> [Gate] Quality verified ({state.quality_score}). Finishing.")
            return "persistence"
        else:
            print(f"   >>> [Gate] Quality insufficient ({state.quality_score}). Refining...")
            return "translate"    

    workflow.add_conditional_edges(
        "evaluate",
        quality_gate,
        {"persistence": "persistence", "translate": "translate"}
    )
    workflow.add_edge("persistence", END)

    # 编译 Graph，开启 checkpointer 用于人机交互
    memory = MemorySaver()
    app = workflow.compile(
        checkpointer=memory, 
        interrupt_after=["search_terms"] 
        # interrupt_before=["translate"] # ★ 关键：在进入翻译前暂停，等待人工修改 glossary
    )
    return app
