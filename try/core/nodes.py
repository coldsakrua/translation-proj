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

# 尝试导入RateLimitError（不同版本的openai可能位置不同）
try:
    from openai import RateLimitError
except ImportError:
    # 如果导入失败，使用通用异常处理
    RateLimitError = Exception  # 使用通用Exception，在代码中通过错误消息判断
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

# (C3) 评估结果结构
class QualityReview(BaseModel):
    score: int = Field(description="1-10分，10分为完美")
    critique: str = Field(description="详细的批评和修改建议")
    pass_flag: bool = Field(description="是否达到出版标准")

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
    critique: Optional[str] = None
    quality_score: Optional[float] = None
    revision_count: int = 0

# ============================================
# 2. 节点实现 (Node Functions)
# ============================================

# --- Node A: 风格与预处理 ---
def node_analyze_style(state: TranslationState):
    print("\n🔹 [Phase A] Analyzing Style & Domain...")
    
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
        print(f"  ⚠️  加载章节摘要失败: {e}")
    
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
        print(f"  ⚠️  加载章节翻译记忆失败: {e}")
    
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
        structured_llm = llm.with_structured_output(StyleMetadata)
        res = structured_llm.invoke(prompt)
        print("----------------------------", res)
        style_data = res.model_dump()
    except Exception as e:
        print(f"⚠️  Structured output failed: {e}")
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
    print("\n🔹 [Phase B1] Mining Terms & Entities...")
    
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
        structured_llm = llm.with_structured_output(RawTerms)
        res = structured_llm.invoke(prompt)
        print("----------------------------", res)
        terms_list = res.terms
    except Exception as e:
        print(f"⚠️  Structured output failed: {e}")
        print("   Falling back to manual JSON parsing...")
        # 回退方案：普通调用 + 手动解析
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
            print(f"⚠️  JSON parsing failed: {je}")
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
                print("   ⚠️  Could not extract terms, using empty list")
    
    state.raw_terms = terms_list
    return {"raw_terms": state.raw_terms}

# --- Node B2: 知识查证 (RAG/Search) ---
def node_search_and_consolidate(state: TranslationState):
    print("\n🔹 [Phase B2] Searching & Standardizing Terms (RAG)...")
    
    consolidated = []
    
    for term in state.raw_terms:
        search_result = retrieve_translation_memory(term, top_k=3)
        term_prompt = f"""
        You are a terminology expert specializing in English-to-Chinese translation.

        Task: Translate the following English term into Chinese (Simplified Chinese).

        Term: "{term}"
        Source text: "{state.source_text}"

        Retrieved translation memory:
        {search_result}

        IMPORTANT: 
        - The "suggested_trans" field MUST be in Chinese (Simplified Chinese), not any other language.
        - If the term is a proper noun or acronym (like "YOLO"), you may keep it as is or provide a Chinese explanation.
        - The "rationale" field should explain your translation choice in Chinese.

        Output a JSON object with ALL fields:
        {{
        "src": string (the original English term),
        "suggested_trans": string (MUST be in Chinese/Simplified Chinese),
        "type": string (e.g., "Terminology", "Acronym", "Proper Noun"),
        "context_meaning": string (explain the meaning in the context, in Chinese),
        "rationale": string (explain translation rationale, in Chinese)
        }}
        """
        try:
            entry = llm.with_structured_output(TermEntry).invoke(term_prompt)
            consolidated.append(entry.model_dump())
        except Exception as e:
            consolidated.append({
                "src": term,
                "suggested_trans": term,
                "type": "Unknown",
                "context_meaning": "Insufficient context from retrieval.",
                "rationale": f"Fallback due to error: {e}"
            })
    
    state.glossary = consolidated
    return {"glossary": state.glossary}



# --- Node C1: 多策略翻译与融合 (The Translator) ---
def node_translate_fusion(state: TranslationState):
    iteration = state.revision_count
    print(f"\n🔸 [Phase 2] Translation Generation (Iter {iteration+1})...")
    
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
            print(f"  📚 加载了 {len(global_terms)} 个全局术语")
    
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
    try:
        similar_examples = get_similar_translation_examples(
            state.source_text, state.book_id, top_k=3
        )
        if similar_examples:
            print(f"  📖 找到 {len(similar_examples)} 个相似的翻译示例")
            translation_examples = similar_examples
    except Exception as e:
        print(f"  ⚠️  加载翻译示例失败: {e}")
    
    # 加载之前章节的翻译记忆（用于风格参考）
    previous_memories = []
    try:
        prev_memories = get_previous_chapters_memory(
            state.book_id, state.chapter_id, top_k=3
        )
        if prev_memories:
            print(f"  📝 加载了 {len(prev_memories)} 个之前章节的翻译记忆")
            previous_memories = prev_memories
    except Exception as e:
        print(f"  ⚠️  加载之前章节记忆失败: {e}")
    
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
    - 注意：如果文本中包含LaTeX公式（如 $...$ 或 $$...$$），请保持原样，不要翻译

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
                print(f"  ⚠️  速率限制错误，等待 {wait_time} 秒后重试... (尝试 {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            elif attempt < max_retries - 1:
                print(f"  ⚠️  翻译错误: {e}，等待 {retry_delay} 秒后重试... (尝试 {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
            else:
                print(f"  ❌ 达到最大重试次数，使用原文作为翻译")
                state.combined_translation = state.source_text
                state.revision_count += 1
    
    return {
        "combined_translation": state.combined_translation,
        "revision_count": state.revision_count
    }


# --- Node C2: 回译与 TEaR 评估 ---
def node_tear_evaluation(state: TranslationState):
    print("\n🔸 [Phase 3] TEaR Evaluation (Back-translation & Scoring)...")
    
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
                print(f"  ⚠️  速率限制错误，等待 {wait_time} 秒后重试... (尝试 {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            elif attempt < max_retries - 1:
                print(f"  ⚠️  回译错误: {e}，等待 {retry_delay} 秒后重试... (尝试 {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
            else:
                print(f"  ❌ 回译失败，跳过回译步骤")
                state.back_translation = state.source_text  # 使用原文作为回译结果
    
    eval_prompt = f"""
    你是翻译质量评估系统。

    请严格按照以下 JSON 格式输出，不要包含任何多余文本：

    {{
    "score": 0-10 的整数,
    "pass_flag": true 或 false,
    "critique": "简要评估意见"
    }}

    【原文】
    {state.source_text}

    【当前译文】
    {state.combined_translation}

    【回译】
    {state.back_translation}
    """
    try:
        eval_res = llm.with_structured_output(QualityReview).invoke(eval_prompt)
        quality_score = eval_res.score
        critique = eval_res.critique
        pass_flag = eval_res.pass_flag
    except Exception as e:
        print(f"⚠️  Structured output failed: {e}")
        print("   Using default quality scores...")
        # 回退到默认值
        quality_score = 7.0
        critique = "评估系统暂时不可用，使用默认评分"
        pass_flag = True
    
    state.quality_score = quality_score
    state.critique = critique
    
    print(f"   >>> Score: {quality_score}/10 | Pass: {pass_flag}")
    return {
        "back_translation": state.back_translation,
        "quality_score": state.quality_score,
        "critique": state.critique
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
    except AttributeError:
        # 万一 LangGraph 传进来的是个 dict（通常不会，除非配置改了）
        book_id = state.get("book_id")
        chapter_id = state.get("chapter_id")
        chunk_id = state.get("chunk_id")
        translation = state.get("combined_translation")
        source_text = state.get("source_text")
        quality_score = state.get("quality_score")
        glossary = state.get("glossary")

    print(f"💾 [Persistence] Writing data for Chunk {chunk_id}...")

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
        "glossary": glossary
    }

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=2)
    
    print(f"📂 File saved: {file_path}")
    
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
        print(f"  ✅ 翻译记忆已保存到Memory系统")
    except Exception as e:
        print(f"  ⚠️  保存翻译记忆失败: {e}")
    
    return {"need_human_review": False}