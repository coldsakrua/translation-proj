from typing import Annotated, List, Dict, TypedDict, Union, Optional
from enum import Enum

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
# from langchain_core.pydantic_v1 import BaseModel, Field
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

from .get_llm import llm
from rag.es_retriever import retrieve_translation_memory
from utils.memory_storage import (
    get_previous_chapters_memory,
    get_similar_translation_examples,
    get_previous_chapter_summaries,
    get_chapter_translation_memory
)

from typing import Any

import json
import os
import time
from collections import deque
from threading import Lock

# 尝试导入RateLimitError（不同版本的openai可能位置不同）
try:
    from openai import RateLimitError
except ImportError:
    # 如果导入失败，使用通用异常处理
    RateLimitError = Exception  # 使用通用Exception，在代码中通过错误消息判断

# ============================================
# 速率限制器：防止超过每分钟20次调用
# ============================================
class RateLimiter:
    """
    速率限制器，确保不超过每分钟20次调用
    当 enable_human_review=False 时使用
    """
    def __init__(self, max_calls_per_minute=20):
        self.max_calls_per_minute = max_calls_per_minute
        self.min_interval = 60.0 / max_calls_per_minute  # 每次调用之间的最小间隔（秒）
        self.call_times = deque()  # 存储最近调用的时间戳
        self.lock = Lock()  # 线程锁，确保线程安全
    
    def wait_if_needed(self, enable_human_review=True):
        """
        如果需要，等待以确保不超过速率限制
        
        Args:
            enable_human_review: 如果为 False，则应用速率限制
        """
        if enable_human_review:
            # 如果启用了人工审查，不需要速率限制
            return
        
        with self.lock:
            current_time = time.time()
            
            # 移除超过1分钟的旧记录
            while self.call_times and current_time - self.call_times[0] > 60:
                self.call_times.popleft()
            
            # 如果已经达到限制，等待
            if len(self.call_times) >= self.max_calls_per_minute:
                # 计算需要等待的时间（直到最早的调用超过1分钟）
                wait_time = 60 - (current_time - self.call_times[0]) + 0.1  # 加0.1秒缓冲
                if wait_time > 0:
                    print(f"  [Rate Limit] 等待 {wait_time:.1f} 秒以避免超过速率限制...")
                    time.sleep(wait_time)
                    # 更新当前时间
                    current_time = time.time()
                    # 清理过期记录
                    while self.call_times and current_time - self.call_times[0] > 60:
                        self.call_times.popleft()
            
            # 确保调用间隔至少为 min_interval
            if self.call_times:
                last_call_time = self.call_times[-1]
                time_since_last = current_time - last_call_time
                if time_since_last < self.min_interval:
                    wait_time = self.min_interval - time_since_last
                    print(f"  [Rate Limit] 等待 {wait_time:.1f} 秒以保持调用间隔...")
                    time.sleep(wait_time)
                    current_time = time.time()
            
            # 记录本次调用时间
            self.call_times.append(current_time)

# 创建全局速率限制器实例
_rate_limiter = RateLimiter(max_calls_per_minute=20)
# ============================================
# 1. 定义数据结构 (State & Pydantic Models)
# ============================================

# (A2) 风格元数据结构
class StyleMetadata(BaseModel):
    domain: str = Field(description="文本领域，如法律、文学、说唱")
    tone: str = Field(description="语体风格，如正式、口语、幽默")
    complexity: str = Field(description="文本复杂度")

# (B1) 术语条目结构
class TermEntry(BaseModel):
    src: str = Field(description="原文词汇（英文）")
    type: str = Field(description="类型: NER/Term/Idiom/Slang/Acronym/Proper Noun")
    context_meaning: Optional[str] = Field(description="语境下的含义（中文）")
    suggested_trans: str = Field(description="建议译法（必须是中文简体）")
    rationale: str = Field(description="翻译理由或策略（中文）")

class TermList(BaseModel):
    terms: List[TermEntry]

# (C3) 评估结果结构（增强版）
class QualityReview(BaseModel):
    score: int = Field(description="1-10分，10分为完美")
    critique: str = Field(description="详细的批评和修改建议")
    pass_flag: bool = Field(description="是否达到出版标准")
    error_types: List[str] = Field(default_factory=list, description="错误类型列表，如：术语错误、语义偏差、语法问题等")
    specific_issues: List[str] = Field(default_factory=list, description="具体问题列表，指出需要修正的具体位置和内容")
    improvement_suggestions: List[str] = Field(default_factory=list, description="改进建议列表，提供具体的修正方向")

class Book:
    book_id: str
    meta: dict
    chapters: List["Chapter"]
class Chapter:
    chapter_id: int
    title: str
    chunks: List["Chunk"]
    memory: Dict[str, str]   # 本章累计总结
class Chunk:
    chunk_id: int
    text: str
    translation: Optional[str]

# --- LangGraph 全局状态 ---
class TranslationState(BaseModel):
    # ======== 核心输入（必须） ========
    book_id: str
    chapter_id: int
    chunk_id: int
    source_text: str
    thread_id: str
    # ===== 上下文 =====
    book_meta: Dict[str, Any] = Field(default_factory=dict)
    chapter_memory: List[str] = Field(default_factory=list)
    global_glossary: Dict[str, Any] = Field(default_factory=dict)      # 全书术语表
    rag_context: List[str] = Field(default_factory=list)              # ES / 外部检索结果
    # ===== 中间结果 =====
    style_guide: Dict[str, Any] = Field(default_factory=dict)
    raw_terms: List[str] = Field(default_factory=list) # 初步识别的难词
    glossary: List[Dict[str, Any]] = Field(default_factory=list) # (B3) 经过查证和人工确认的术语表
    # ===== 翻译结果 =====
    draft_versions: List[str] = Field(default_factory=list) # 直译/意译/风格化版本
    combined_translation: Optional[str] = None # 融合后的译文
    back_translation: Optional[str] = None # 回译文
    # ===== 控制信号 =====
    need_human_review: bool = True
    enable_human_review: bool = True  # 是否启用人工审查模式（用于控制速率限制）
    use_rag: bool = True  # 是否使用 RAG 检索（默认启用）
    critique: Optional[str] = None
    quality_score: Optional[float] = None
    revision_count: int = 0
    refinement_history: List[Dict[str, Any]] = Field(default_factory=list)  # 修正历史记录

# ============================================
# 2. 节点实现 (Node Functions)
# ============================================

# --- Node A: 风格与预处理 ---
def node_analyze_style(state: TranslationState):
    print("\n[Phase A] Analyzing Style & Domain...")
    
    # 加载章节上下文（之前的章节摘要和翻译记忆）
    chapter_context_parts = []
    
    # 1. 加载之前章节的摘要
    try:
        prev_summaries = get_previous_chapter_summaries(state.book_id, state.chapter_id)
        if prev_summaries:
            summary_text = "\n".join([
                f"第{summ['chapter_id']}章摘要: {summ['summary']}" 
                for summ in prev_summaries[-2:]  # 只取最近2章
            ])
            chapter_context_parts.append(f"之前章节摘要:\n{summary_text}")
    except Exception as e:
        print(f"  [WARNING] 加载章节摘要失败: {e}")
    
    # 2. 加载当前章节已翻译的chunk（用于上下文）
    try:
        current_chapter_memories = get_chapter_translation_memory(
            state.book_id, state.chapter_id
        )
        # 只取当前chunk之前的翻译记忆
        prev_chunks = [
            mem for mem in current_chapter_memories 
            if mem.get('chunk_id', -1) < state.chunk_id
        ]
        if prev_chunks:
            context_text = "\n".join([
                f"Chunk {mem['chunk_id']}: {mem['source_text'][:100]}... → {mem['translation'][:100]}..."
                for mem in prev_chunks[-3:]  # 只取最近3个chunk
            ])
            chapter_context_parts.append(f"本章已翻译内容:\n{context_text}")
    except Exception as e:
        print(f"  [WARNING] 加载章节翻译记忆失败: {e}")
    
    # 3. 使用state中的chapter_memory（如果有）
    if state.chapter_memory:
        chapter_context_parts.append("\n".join(state.chapter_memory))
    
    chapter_ctx = "\n\n".join(chapter_context_parts) if chapter_context_parts else "无"
    
    prompt = f"""
    分析以下文本的领域、语体风格和复杂度。
    参考上下文脉络：{chapter_ctx}
    当前文本：{state.source_text}
    
    请严格按照以下 JSON 格式输出：
    {{
        "domain": "领域",
        "tone": "语体风格",
        "complexity": "复杂度"
    }}
    """
    # 结构化输出
    try:
        # 速率限制检查（如果禁用了人工审查）
        _rate_limiter.wait_if_needed(state.enable_human_review)
        structured_llm = llm.with_structured_output(StyleMetadata)
        res = structured_llm.invoke(prompt)
        print("----------------------------", res)
        style_data = res.model_dump()
    except Exception as e:
        print(f"[WARNING] Structured output failed: {e}")
        print("   Using default style metadata...")
        # 回退到默认值
        style_data = {
            "domain": "通用",
            "tone": "正式",
            "complexity": "中等"
        }
    
    # 直接更新状态属性
    state.style_guide = style_data
    return {"style_guide": state.style_guide}

# --- Node B1: 术语识别 (Term Miner) ---
def node_extract_terms(state: TranslationState):
    print("\n[Phase B1] Mining Terms & Entities...")
    
    domain = state.style_guide.get('domain', '未知领域')
    
    prompt = f"""
    你是术语专家。请识别文本中的：
    1. 命名实体 (NER) - 人名、地名、机构名等
    2. 领域术语 (Domain Terms) - 专业术语、技术词汇
    3. 文化负载词/俚语 (Idioms/Slang) - 习语、俚语等

    重要要求：
    - 只识别英文原文中的词汇，不要识别中文
    - 只输出英文原文词汇，不要输出翻译
    - 仅输出需要查证或统一译名的词汇列表
    - ⚠️ 注意：人名（如作者名、研究者姓名）虽然会被识别，但在翻译时应保留英文原文，不需要翻译
    
    文本：{state.source_text}
    领域：{domain}
    
    请严格按照以下 JSON 格式输出，不要包含任何多余文本：
    {{
        "terms": ["term1", "term2", "term3"]
    }}
    
    注意：terms数组中的每个元素必须是英文原文，不能是中文翻译。
    """
    class RawTerms(BaseModel):
        terms: List[str]

    try:
        # 速率限制检查（如果禁用了人工审查）
        _rate_limiter.wait_if_needed(state.enable_human_review)
        structured_llm = llm.with_structured_output(RawTerms)
        res = structured_llm.invoke(prompt)
        print("----------------------------", res)
        terms_list = res.terms
    except Exception as e:
        print(f"[WARNING] Structured output failed: {e}")
        print("   Falling back to manual JSON parsing...")
        # 回退方案：普通调用 + 手动解析
        _rate_limiter.wait_if_needed(state.enable_human_review)
        response = llm.invoke(prompt)
        content = response.content.strip()
        
        # 尝试提取 JSON（可能包含 markdown 代码块）
        import re
        json_match = re.search(r'\{[^{}]*"terms"[^{}]*\[[^\]]*\][^{}]*\}', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            # 如果没有找到 JSON，尝试直接解析整个内容
            json_str = content
            if json_str.startswith('```'):
                json_str = json_str.split('```')[1]
                if json_str.startswith('json'):
                    json_str = json_str[4:]
            json_str = json_str.strip()
        
        try:
            import json
            parsed = json.loads(json_str)
            terms_list = parsed.get("terms", [])
        except json.JSONDecodeError as je:
            print(f"[WARNING] JSON parsing failed: {je}")
            print(f"   Raw content: {content[:200]}...")
            # 最后的回退：尝试从文本中提取可能的术语
            terms_list = []
            # 简单提取：查找引号中的内容或大写单词
            import re
            # 提取引号中的内容
            quoted_terms = re.findall(r'"([^"]+)"', content)
            terms_list.extend(quoted_terms)
            # 如果没有找到，返回空列表
            if not terms_list:
                print("   [WARNING] Could not extract terms, using empty list")
    
    state.raw_terms = terms_list
    return {"raw_terms": state.raw_terms}

# --- Node B2: 知识查证 (RAG/Search) ---
def node_search_and_consolidate(state: TranslationState):
    if state.use_rag:
        print("\n[Phase B2] Searching & Standardizing Terms (RAG)...")
    else:
        print("\n[Phase B2] Standardizing Terms (Direct Translation, No RAG)...")
    
    consolidated = []
    
    for term in state.raw_terms:
        # 如果启用 RAG，则检索翻译记忆；否则跳过检索
        if state.use_rag:
            search_result = retrieve_translation_memory(term, top_k=3)
            rag_context = f"\n\nRetrieved translation memory:\n{search_result}"
        else:
            search_result = ""
            rag_context = "\n\nNote: RAG retrieval is disabled. Translate based on your knowledge only."
        
        term_prompt = f"""
        You are a terminology expert specializing in English-to-Chinese translation.

        Task: Translate the following English term into Chinese (Simplified Chinese).

        Term: "{term}"
        Source text: "{state.source_text}"
        {rag_context}

        IMPORTANT: 
        - The "suggested_trans" field MUST be in Chinese (Simplified Chinese), not any other language.
        - If the term is a proper noun or acronym (like "YOLO"), you may keep it as is or provide a Chinese explanation.
        - CRITICAL: If the term is a person's name (e.g., "Krizhevsky", "Alex", "John Smith"), you MUST keep it as the original English name in the "suggested_trans" field. Do NOT translate person names into Chinese.
        - The "rationale" field should explain your translation choice in Chinese.

        Output a JSON object with ALL fields:
        {{
        "src": string (the original English term),
        "suggested_trans": string (MUST be in Chinese/Simplified Chinese, EXCEPT for person names which should remain in English),
        "type": string (e.g., "Terminology", "Acronym", "Proper Noun", "Person Name"),
        "context_meaning": string (explain the meaning in the context, in Chinese),
        "rationale": string (explain translation rationale, in Chinese)
        }}
        """
        try:
            # 速率限制检查（如果禁用了人工审查）
            _rate_limiter.wait_if_needed(state.enable_human_review)
            entry = llm.with_structured_output(TermEntry).invoke(term_prompt)
            consolidated.append(entry.model_dump())
        except Exception as e:
            consolidated.append({
                "src": term,
                "suggested_trans": term,
                "type": "Unknown",
                "context_meaning": "Insufficient context from retrieval." if state.use_rag else "Direct translation without RAG.",
                "rationale": f"Fallback due to error: {e}"
            })
    
    state.glossary = consolidated
    return {"glossary": state.glossary}



# --- Node C1: 多策略翻译与融合 (The Translator) ---
def node_translate_fusion(state: TranslationState):
    iteration = state.revision_count
    print(f"\n[Phase 2] Translation Generation (Iter {iteration+1})...")
    
    # 直接使用原文，不再提取LaTeX公式
    source_text_cleaned = state.source_text
    
    # 加载全局术语表（跨章节）
    global_glossary_text = ""
    if state.global_glossary:
        global_terms = []
        for term_key, term_info in state.global_glossary.items():
            if isinstance(term_info, dict):
                src = term_info.get('src', term_key)
                trans = term_info.get('suggested_trans', '')
                if src and trans:
                    global_terms.append(f"- {src} -> {trans}")
        if global_terms:
            global_glossary_text = "\n".join(global_terms[:20])  # 限制数量
            print(f"  加载了 {len(global_terms)} 个全局术语")
    
    # 当前chunk的术语表
    current_glossary_text = "\n".join([
        f"- {t['src']} -> {t['suggested_trans']} ({t.get('rationale', '')})" 
        for t in state.glossary
    ])
    
    # 合并术语表
    all_glossary_text = ""
    if global_glossary_text:
        all_glossary_text += f"【全局术语表（来自之前章节）】\n{global_glossary_text}\n\n"
    if current_glossary_text:
        all_glossary_text += f"【当前章节术语表】\n{current_glossary_text}"
    
    style_str = str(state.style_guide)
    prev_feedback = state.critique or "无"
    
    # 加载相似的翻译示例（从已翻译的文本中）
    translation_examples = []
    if state.use_rag:
        try:
            similar_examples = get_similar_translation_examples(
                state.source_text, state.book_id, top_k=3
            )
            if similar_examples:
                print(f"  找到 {len(similar_examples)} 个相似的翻译示例")
                translation_examples = similar_examples
        except Exception as e:
            print(f"  [WARNING] 加载翻译示例失败: {e}")
    else:
        print(f"  跳过翻译示例检索（RAG已禁用）")
    
    # 加载之前章节的翻译记忆（用于风格参考）
    previous_memories = []
    if state.use_rag:
        try:
            prev_memories = get_previous_chapters_memory(
                state.book_id, state.chapter_id, top_k=3
            )
            if prev_memories:
                print(f"  加载了 {len(prev_memories)} 个之前章节的翻译记忆")
                previous_memories = prev_memories
        except Exception as e:
            print(f"  [WARNING] 加载之前章节记忆失败: {e}")
    else:
        print(f"  跳过之前章节记忆检索（RAG已禁用）")
    
    # 构建翻译示例文本
    examples_text = ""
    if translation_examples:
        examples_text = "\n【相似翻译示例（参考这些已翻译的文本对）】\n"
        for i, ex in enumerate(translation_examples, 1):
            examples_text += f"\n示例{i}:\n原文: {ex['source_text'][:200]}...\n译文: {ex['translation'][:200]}...\n"
    
    if previous_memories:
        examples_text += "\n【之前章节的翻译风格参考】\n"
        for i, mem in enumerate(previous_memories, 1):
            examples_text += f"\n参考{i}:\n原文: {mem['source_text'][:150]}...\n译文: {mem['translation'][:150]}...\n"
    
    # 多步骤引导翻译的prompt
    prompt = f"""
你是一个高级翻译引擎，需要参考已翻译的文本对来保持翻译风格的一致性。

【翻译步骤】
请严格按照以下步骤执行：

步骤1：理解与解构
- 仔细分析原文的句子结构、语法关系和语义层次
- 识别关键信息点和逻辑连接
- 注意：文本中的 __LATEX_PLACEHOLDER_X__ 是LaTeX公式占位符，请保持原样

步骤2：参考已翻译文本
- 仔细研究下面提供的已翻译文本对
- 学习其翻译风格、术语使用和表达方式
- 确保当前翻译与已有翻译保持风格一致

步骤3：多版本生成（在脑海中）
- 直译版：尽可能贴近原文结构，保留原文的表达方式
- 意译版：根据目标语言习惯调整表达，使译文更自然流畅
- 风格化版：结合已翻译文本的风格，保持全书一致性

步骤4：融合与润色
- 结合直译和意译的优点
- 参考已翻译文本的风格和术语使用
- 确保术语使用与术语表完全一致
- 生成最终译文

【约束条件】
- 严格遵守风格：{style_str}
- 强制使用术语表（必须严格遵守）：
{all_glossary_text if all_glossary_text else "无术语表"}
    - 上一轮反馈（如有）：{prev_feedback}
{f"重要：这是根据用户反馈的重新翻译，请特别注意以下反馈意见并据此改进翻译：{prev_feedback}" if (state.critique and state.critique != "无" and state.revision_count == 0) else ""}
    - 注意：如果文本中包含LaTeX公式（如 $...$ 或 $$...$$），请保持原样，不要翻译
    - 重要：人名（包括作者名、研究者姓名等）必须保留英文原文，不要翻译成中文。例如："Krizhevsky"、"Alex"、"John Smith" 等应保持原样

{examples_text if examples_text else ""}

【待翻译原文】
{source_text_cleaned}

请只输出最终融合后的译文，不要输出中间步骤。
"""
    
    # 添加重试机制
    max_retries = 3
    retry_delay = 2  # 秒
    for attempt in range(max_retries):
        try:
            # 速率限制检查（如果禁用了人工审查）
            _rate_limiter.wait_if_needed(state.enable_human_review)
            response = llm.invoke(prompt)
            translated_text = response.content
            state.combined_translation = translated_text
            state.revision_count += 1
            print("----------------------------", translated_text)
            break
        except Exception as e:
            # 检查是否是速率限制错误
            error_str = str(e)
            is_rate_limit = "RateLimitError" in str(type(e).__name__) or "rate_limit" in error_str.lower() or "429" in error_str
            
            if is_rate_limit and attempt < max_retries - 1:
                wait_time = retry_delay * (attempt + 1)
                print(f"  [WARNING] 速率限制错误，等待 {wait_time} 秒后重试... (尝试 {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            elif attempt < max_retries - 1:
                print(f"  [WARNING] 翻译错误: {e}，等待 {retry_delay} 秒后重试... (尝试 {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
            else:
                print(f"  × 达到最大重试次数，使用原文作为翻译")
                state.combined_translation = state.source_text
                state.revision_count += 1
    
    return {
        "combined_translation": state.combined_translation,
        "revision_count": state.revision_count
    }


# --- Node C2: 回译与 TEaR 评估 ---
def node_tear_evaluation(state: TranslationState):
    print("\n[Phase 3] TEaR Evaluation (Back-translation & Scoring)...")
    
    # 直接使用翻译结果，不再提取LaTeX公式
    translation_cleaned = state.combined_translation
    
    bt_prompt = f"""Translate the following text back to the source language (English) strictly.
Note: If the text contains LaTeX formulas (like $...$ or $$...$$), keep them unchanged, do not translate them.

Text to translate:
{translation_cleaned}"""
    
    # 添加重试机制处理速率限制
    max_retries = 3
    retry_delay = 2
    back_translation = None
    
    for attempt in range(max_retries):
        try:
            # 速率限制检查（如果禁用了人工审查）
            _rate_limiter.wait_if_needed(state.enable_human_review)
            bt_res = llm.invoke(bt_prompt)
            back_translation = bt_res.content
            state.back_translation = back_translation
            break
        except Exception as e:
            # 检查是否是速率限制错误
            error_str = str(e)
            is_rate_limit = "RateLimitError" in str(type(e).__name__) or "rate_limit" in error_str.lower() or "429" in error_str
            
            if is_rate_limit and attempt < max_retries - 1:
                wait_time = retry_delay * (attempt + 1)
                print(f"  [WARNING] 速率限制错误，等待 {wait_time} 秒后重试... (尝试 {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            elif attempt < max_retries - 1:
                print(f"  [WARNING] 回译错误: {e}，等待 {retry_delay} 秒后重试... (尝试 {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
            else:
                print(f"  × 回译失败，跳过回译步骤")
                state.back_translation = state.source_text  # 使用原文作为回译结果
    
    # 构建术语表文本（用于评估）
    glossary_text = ""
    if state.glossary:
        glossary_text = "\n".join([
            f"- {t['src']} -> {t['suggested_trans']}" 
            for t in state.glossary[:20]
        ])
    
    eval_prompt = f"""
    你是专业的翻译质量评估系统，需要对翻译进行多维度评估。

    请仔细对比原文、译文和回译文，识别以下问题：
    1. **术语一致性**：译文中的术语是否与术语表一致
    2. **语义准确性**：译文是否准确传达了原文的意思
    3. **回译一致性**：回译文与原文的相似度如何
    4. **语言流畅性**：译文是否符合中文表达习惯
    5. **风格一致性**：译文是否与已翻译文本保持风格一致

    【术语表（必须严格遵守）】
    {glossary_text if glossary_text else "无术语表"}

    【原文】
    {state.source_text}

    【当前译文】
    {state.combined_translation}

    【回译文】
    {state.back_translation}

    请按照以下格式输出评估结果：
    {{
        "score": 0-10的整数（10分为完美）,
        "pass_flag": true或false（是否达到出版标准，通常7分以上为true）,
        "critique": "总体评估意见，包括优点和主要问题",
        "error_types": ["错误类型1", "错误类型2"]（如：["术语不一致", "语义偏差", "语法问题"]）,
        "specific_issues": ["具体问题1：指出具体位置和内容", "具体问题2：..."],
        "improvement_suggestions": ["改进建议1：如何修正", "改进建议2：..."]
    }}

    注意：
    - error_types应该具体明确，如"术语不一致"、"语义偏差"、"语法错误"、"流畅性问题"等
    - specific_issues应该指出具体的问题位置和内容，便于修正
    - improvement_suggestions应该提供可操作的修正建议
    """
    try:
        eval_res = llm.with_structured_output(QualityReview).invoke(eval_prompt)
        quality_score = eval_res.score
        critique = eval_res.critique
        pass_flag = eval_res.pass_flag
        error_types = eval_res.error_types or []
        specific_issues = eval_res.specific_issues or []
        improvement_suggestions = eval_res.improvement_suggestions or []
    except Exception as e:
        print(f"[WARNING] Structured output failed: {e}")
        print("   Using default quality scores...")
        # 回退到默认值
        quality_score = 7.0
        critique = "评估系统暂时不可用，使用默认评分"
        pass_flag = True
        error_types = []
        specific_issues = []
        improvement_suggestions = []
    
    state.quality_score = quality_score
    state.critique = critique
    
    # 保存详细的评估信息到refinement_history
    evaluation_detail = {
        "iteration": state.revision_count,
        "score": quality_score,
        "critique": critique,
        "error_types": error_types,
        "specific_issues": specific_issues,
        "improvement_suggestions": improvement_suggestions,
        "back_translation": state.back_translation
    }
    state.refinement_history.append(evaluation_detail)
    
    print(f"   >>> Score: {quality_score}/10 | Pass: {pass_flag}")
    if error_types:
        print(f"   >>> 错误类型: {', '.join(error_types)}")
    if specific_issues:
        print(f"   >>> 主要问题: {specific_issues[0] if specific_issues else '无'}")
    
    return {
        "back_translation": state.back_translation,
        "quality_score": state.quality_score,
        "critique": state.critique,
        "refinement_history": state.refinement_history
    }

# --- Node C3: 基于评估结果的针对性修正 (Refine) ---
def node_refine_translation(state: TranslationState):
    """
    TEaR框架的Refine步骤：基于评估反馈进行针对性修正
    """
    iteration = state.revision_count
    print(f"\n[Phase 4] Refinement (Iter {iteration+1})...")
    
    # 获取最新的评估信息
    if not state.refinement_history:
        print("  [WARNING] 没有评估历史，跳过修正步骤")
        return {"combined_translation": state.combined_translation}
    
    latest_eval = state.refinement_history[-1]
    critique = latest_eval.get("critique", "")
    error_types = latest_eval.get("error_types", [])
    specific_issues = latest_eval.get("specific_issues", [])
    improvement_suggestions = latest_eval.get("improvement_suggestions", [])
    
    # 构建问题总结
    issues_summary = ""
    if specific_issues:
        issues_summary = "\n".join([f"- {issue}" for issue in specific_issues])
    
    suggestions_summary = ""
    if improvement_suggestions:
        suggestions_summary = "\n".join([f"- {suggestion}" for suggestion in improvement_suggestions])
    
    # 加载术语表
    glossary_text = ""
    if state.glossary:
        glossary_text = "\n".join([
            f"- {t['src']} -> {t['suggested_trans']}" 
            for t in state.glossary
        ])
    
    # 加载全局术语表
    global_glossary_text = ""
    if state.global_glossary:
        global_terms = []
        for term_key, term_info in state.global_glossary.items():
            if isinstance(term_info, dict):
                src = term_info.get('src', term_key)
                trans = term_info.get('suggested_trans', '')
                if src and trans:
                    global_terms.append(f"- {src} -> {trans}")
        if global_terms:
            global_glossary_text = "\n".join(global_terms[:20])
    
    all_glossary_text = ""
    if global_glossary_text:
        all_glossary_text += f"【全局术语表】\n{global_glossary_text}\n\n"
    if glossary_text:
        all_glossary_text += f"【当前章节术语表】\n{glossary_text}"
    
    style_str = str(state.style_guide)
    
    # 构建修正提示词
    refine_prompt = f"""
    你是专业的翻译修正专家。当前译文已经过评估，发现了一些问题，需要你进行针对性修正。

    【修正原则】
    1. **针对性修正**：只修正评估中发现的具体问题，不要大幅改动
    2. **保持优点**：保留译文中正确的部分，不要过度修改
    3. **术语一致性**：严格遵循术语表，确保术语翻译一致
    4. **语义准确性**：确保修正后的译文准确传达原文意思
    5. **语言流畅性**：确保修正后的译文符合中文表达习惯

    【评估反馈】
    总体评估：{critique}
    
    错误类型：{', '.join(error_types) if error_types else '无'}
    
    具体问题：
    {issues_summary if issues_summary else "无具体问题"}
    
    改进建议：
    {suggestions_summary if suggestions_summary else "无具体建议"}

    【术语表（必须严格遵守）】
    {all_glossary_text if all_glossary_text else "无术语表"}

    【风格要求】
    {style_str}

    【原文】
    {state.source_text}

    【当前译文（需要修正）】
    {state.combined_translation}

    【回译文（用于参考）】
    {state.back_translation}

    【修正步骤】
    1. 仔细阅读评估反馈，理解具体问题
    2. 对照原文和回译文，识别语义偏差
    3. 检查术语使用是否与术语表一致
    4. 针对性地修正发现的问题
    5. 确保修正后的译文流畅自然

    【注意事项】
    - 只修正评估中发现的问题，不要做不必要的改动
    - 如果术语表中有对应术语，必须使用术语表中的翻译
    - 保持译文的整体风格和结构
    - 如果文本中包含LaTeX公式（如 $...$ 或 $$...$$），请保持原样
    - 重要：人名（包括作者名、研究者姓名等）必须保留英文原文，不要翻译成中文

    请输出修正后的完整译文：
    """
    
    # 执行修正
    max_retries = 3
    retry_delay = 2
    for attempt in range(max_retries):
        try:
            # 速率限制检查（如果禁用了人工审查）
            _rate_limiter.wait_if_needed(state.enable_human_review)
            response = llm.invoke(refine_prompt)
            refined_translation = response.content.strip()
            state.combined_translation = refined_translation
            state.revision_count += 1
            print(f"  √ 修正完成（迭代 {state.revision_count}）")
            break
        except Exception as e:
            error_str = str(e)
            is_rate_limit = "RateLimitError" in str(type(e).__name__) or "rate_limit" in error_str.lower() or "429" in error_str
            
            if is_rate_limit and attempt < max_retries - 1:
                wait_time = retry_delay * (attempt + 1)
                print(f"  [WARNING] 速率限制错误，等待 {wait_time} 秒后重试... (尝试 {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            elif attempt < max_retries - 1:
                print(f"  [WARNING] 修正错误: {e}，等待 {retry_delay} 秒后重试... (尝试 {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
            else:
                print(f"  × 达到最大重试次数，保持原译文")
                # 保持原译文不变
                state.revision_count += 1
    
    return {
        "combined_translation": state.combined_translation,
        "revision_count": state.revision_count
    }

# --- Node D: 持久化保存 ---
def node_persistence(state: TranslationState):
    """保存最终翻译结果到本地文件"""
    
    # 既然 state 是 TranslationState 类型，直接点号访问最安全
    try:
        book_id = state.book_id
        chapter_id = state.chapter_id
        chunk_id = state.chunk_id
        translation = state.combined_translation
        source_text = state.source_text
        quality_score = state.quality_score
        glossary = state.glossary
        refinement_history = state.refinement_history
        revision_count = state.revision_count
    except AttributeError:
        # 万一 LangGraph 传进来的是个 dict（通常不会，除非配置改了）
        book_id = state.get("book_id")
        chapter_id = state.get("chapter_id")
        chunk_id = state.get("chunk_id")
        translation = state.get("combined_translation")
        source_text = state.get("source_text")
        quality_score = state.get("quality_score")
        glossary = state.get("glossary")
        refinement_history = state.get("refinement_history", [])
        revision_count = state.get("revision_count", 0)

    print(f"[Persistence] Writing data for Chunk {chunk_id}...")

    # 检查source_text是否为空，如果为空则跳过保存
    if not source_text or not source_text.strip():
        print(f"  [WARNING] Chunk {chunk_id} 的source_text为空，跳过保存")
        return {"need_human_review": False}

    # 路径构造
    base_dir = f"./output/{book_id}/chapter_{chapter_id}"
    os.makedirs(base_dir, exist_ok=True)
    
    # 建议 chunk_id 格式化为 3 位或 4 位数字，方便排序
    file_path = os.path.join(base_dir, f"chunk_{int(chunk_id):03d}.json")
    
    data_to_save = {
        "chunk_id": chunk_id,
        "source_text": source_text,
        "translation": translation,
        "quality_score": quality_score,
        "glossary": glossary,
        "refinement_history": state.refinement_history,  # 保存修正历史
        "revision_count": state.revision_count  # 保存迭代次数
    }

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=2)
    
    print(f"File saved: {file_path}")
    
    # 保存翻译记忆到Memory系统
    try:
        from utils.memory_storage import save_translation_memory
        save_translation_memory(
            book_id=book_id,
            chapter_id=chapter_id,
            chunk_id=chunk_id,
            source_text=source_text,
            translation=translation,
            quality_score=quality_score
        )
        print(f"  √ 翻译记忆已保存到Memory系统")
    except Exception as e:
        print(f"  [WARNING] 保存翻译记忆失败: {e}")
    
    return {"need_human_review": False}