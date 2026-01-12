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
    workflow.add_node("refine", node_refine_translation)  # 新增：专门的修正节点
    workflow.add_node("persistence", node_persistence)

    # 构建流程连线
    workflow.add_edge(START, "analyze_style")
    workflow.add_edge("analyze_style", "extract_terms")
    workflow.add_edge("extract_terms", "search_terms")

    # --- 工作流连接（已改为chapter级别审查，不再逐chunk中断） ---
    # 原逻辑：在 search_terms 结束后暂停，让人类检查 glossary（已注释）
    # 新逻辑：完整执行所有chunk，chapter完成后统一审查术语表
    workflow.add_edge("search_terms", "translate")

    # --- 根据 use_rag 决定是否跳过 TEaR 环节 ---
    def translate_gate(state: TranslationState):
        """
        翻译后门控：决定是否跳过 TEaR 环节
        - 如果 use_rag=False，直接保存，跳过评估和优化
        - 如果 use_rag=True，进入评估环节
        """
        if not state.use_rag:
            print(f"   >>> [Gate] RAG disabled, skipping TEaR loop. Directly saving translation.")
            return "persistence"
        else:
            return "evaluate"

    workflow.add_conditional_edges(
        "translate",
        translate_gate,
        {
            "persistence": "persistence",
            "evaluate": "evaluate"
        }
    )

    # --- TEaR循环逻辑 (Router) ---
    def quality_gate(state: TranslationState):
        """
        质量门控：决定是否需要继续修正
        - 如果质量达标（>=7分）或达到最大迭代次数，则保存
        - 如果质量不达标，则进入refine节点进行针对性修正
        """
        # 限制最大迭代次数防止死循环
        if state.revision_count >= 3:
            print(f"   >>> [Gate] Max iterations reached ({state.revision_count}). Force stop.")
            return "persistence"
        
        # 质量达标，保存结果
        if state.quality_score is not None and state.quality_score >= 7:
            print(f"   >>> [Gate] Quality verified (Score: {state.quality_score}/10). Finishing.")
            return "persistence"
        
        # 质量不达标，进入refine节点进行针对性修正
        else:
            score_display = state.quality_score if state.quality_score is not None else "N/A"
            print(f"   >>> [Gate] Quality insufficient (Score: {score_display}/10). Entering refine step...")
            
            # 如果有评估历史，说明已经评估过，应该进入refine
            if state.refinement_history:
                return "refine"
            else:
                # 如果没有评估历史，说明是第一次翻译，直接进入refine（这种情况不应该发生）
                return "refine"

    workflow.add_conditional_edges(
        "evaluate",
        quality_gate,
        {
            "persistence": "persistence", 
            "refine": "refine"  # 改为refine节点而不是translate
        }
    )
    
    # refine节点完成后，重新评估
    workflow.add_edge("refine", "evaluate")
    workflow.add_edge("persistence", END)

    # 编译 Graph，开启 checkpointer（不再中断，完整执行）
    memory = MemorySaver()
    app = workflow.compile(
        checkpointer=memory
        # 已移除 interrupt_after，改为 chapter 级别统一审查
    )
    return app
