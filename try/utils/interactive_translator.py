"""
对话式翻译模块
支持用户输入文本和要求，进行翻译，并保存结果
支持严谨/通俗两种翻译风格
"""
import json
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.get_llm import llm
from rag.es_retriever import retrieve_translation_memory
from utils.glossary_storage import load_reviewed_glossary


def translate_with_style(
    source_text: str,
    translation_style: str = "rigorous",
    user_requirements: Optional[str] = None,
    book_id: str = "interactive",
    use_glossary: bool = True
) -> Dict[str, Any]:
    """
    根据指定风格翻译文本
    
    Args:
        source_text: 待翻译的原文
        translation_style: 翻译风格，"rigorous"（严谨）或 "popular"（通俗）
        user_requirements: 用户额外要求
        book_id: 书籍ID，用于加载全局术语表
        use_glossary: 是否使用术语表
    
    Returns:
        包含翻译结果的字典
    """
    
    # 加载全局术语表
    glossary_text = ""
    if use_glossary:
        try:
            reviewed_glossary = load_reviewed_glossary()
            if reviewed_glossary:
                glossary_terms = []
                for term_key, term_info in reviewed_glossary.items():
                    if isinstance(term_info, dict):
                        src = term_info.get('src', term_key)
                        trans = term_info.get('suggested_trans', '')
                        if src and trans:
                            glossary_terms.append(f"- {src} -> {trans}")
                if glossary_terms:
                    glossary_text = "\n".join(glossary_terms[:30])  # 限制数量
        except Exception as e:
            print(f"  [WARNING] 加载术语表失败: {e}")
    
    # 从RAG检索相关翻译记忆
    rag_context = ""
    try:
        # 提取关键词进行检索
        keywords = source_text.split()[:5]  # 取前5个词
        for keyword in keywords:
            if len(keyword) > 3:  # 只检索长度>3的词
                search_result = retrieve_translation_memory(keyword, top_k=2)
                if search_result and search_result.strip():
                    rag_context += f"\n相关翻译记忆（关键词: {keyword}）:\n{search_result[:300]}...\n"
                    break  # 只取第一个有效结果
    except Exception as e:
        print(f"  [WARNING] RAG检索失败: {e}")
    
    # 根据风格设置不同的提示词
    if translation_style == "rigorous":
        style_instruction = """
【翻译风格：严谨学术风格】
- 保持专业术语的准确性和一致性
- 使用规范的学术表达方式
- 保留原文的严谨性和精确性
- 适合AI论文、技术文档等专业领域翻译
- 术语必须严格按照术语表翻译，不得随意更改
"""
    else:  # popular
        style_instruction = """
【翻译风格：通俗易懂风格】
- 减少专业术语，使用更通俗的表达
- 将复杂概念转化为易于理解的语言
- 保持原文意思准确，但表达更自然流畅
- 适合科普文章、教学材料等需要降低理解门槛的场景
- 对于专业术语，可以适当添加解释或使用更通俗的替代词
"""
    
    # 构建翻译提示词
    prompt = f"""
你是一个专业的AI论文翻译专家，擅长将英文AI/机器学习论文翻译成中文。

{style_instruction}

【翻译步骤】
1. 理解原文：仔细分析原文的句子结构、语法关系和语义层次
2. 术语处理：
   - 识别专业术语和技术词汇
   - 参考术语表（如有）确保术语翻译的一致性
   - 如果是通俗风格，将专业术语转化为更易理解的表达
3. 翻译生成：
   - 保持原文的准确性和完整性
   - 确保译文符合中文表达习惯
   - 注意：如果文本中包含LaTeX公式（如 $...$ 或 $$...$$），请保持原样，不要翻译
4. 润色优化：
   - 检查术语使用是否一致
   - 确保译文流畅自然
   - 符合目标风格要求

【术语表（必须严格遵守）】
{glossary_text if glossary_text else "无术语表"}

{rag_context if rag_context else ""}

【用户额外要求】
{user_requirements if user_requirements else "无特殊要求"}

【待翻译原文】
{source_text}

请只输出最终译文，不要输出中间步骤或说明。
"""
    
    # 执行翻译
    try:
        response = llm.invoke(prompt)
        translation = response.content.strip()
        
        return {
            "source_text": source_text,
            "translation": translation,
            "translation_style": translation_style,
            "user_requirements": user_requirements,
            "glossary_used": bool(glossary_text),
            "translated_at": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"  × 翻译失败: {e}")
        return {
            "source_text": source_text,
            "translation": f"[翻译失败: {str(e)}]",
            "translation_style": translation_style,
            "error": str(e),
            "translated_at": datetime.now().isoformat()
        }


def save_translation_result(
    translation_result: Dict[str, Any],
    book_id: str = "interactive",
    output_dir: Optional[str] = None
) -> str:
    """
    保存翻译结果到文件（格式与chunk文件一致）
    
    Args:
        translation_result: 翻译结果字典
        book_id: 书籍ID
        output_dir: 输出目录，如果为None则使用默认路径
    
    Returns:
        保存的文件路径
    """
    if output_dir is None:
        output_dir = f"output/{book_id}/interactive"
    
    # 确保目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 生成文件名（使用时间戳）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"translation_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    # 构建保存的数据结构（与chunk文件格式一致）
    data_to_save = {
        "chunk_id": f"interactive_{timestamp}",
        "source_text": translation_result["source_text"],
        "translation": translation_result["translation"],
        "translation_style": translation_result.get("translation_style", "rigorous"),
        "user_requirements": translation_result.get("user_requirements"),
        "glossary_used": translation_result.get("glossary_used", False),
        "quality_score": None,  # 交互式翻译不进行质量评分
        "saved_at": translation_result.get("translated_at", datetime.now().isoformat())
    }
    
    # 如果有错误，也保存
    if "error" in translation_result:
        data_to_save["error"] = translation_result["error"]
    
    # 保存到文件
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        return filepath
    except Exception as e:
        print(f"  × 保存文件失败: {e}")
        return ""


def interactive_translate_loop():
    """
    交互式翻译循环
    """
    print("\n" + "="*60)
    print("🤖 对话式AI论文翻译系统")
    print("="*60)
    print("\n功能说明：")
    print("  - 输入英文文本进行翻译")
    print("  - 支持严谨/通俗两种翻译风格")
    print("  - 可以添加额外要求")
    print("  - 翻译结果自动保存")
    print("\n命令：")
    print("  - 输入文本：直接输入待翻译的英文文本")
    print("  - 切换风格：输入 'style:rigorous' 或 'style:popular'")
    print("  - 添加要求：输入 'req:你的要求'")
    print("  - 退出：输入 'quit' 或 'exit'")
    print("  - 帮助：输入 'help'")
    print("-"*60 + "\n")
    
    current_style = "rigorous"  # 默认严谨风格
    current_requirements = None
    translation_count = 0
    
    while True:
        try:
            # 显示当前设置
            style_display = "严谨" if current_style == "rigorous" else "通俗"
            print(f"\n[当前设置: 风格={style_display}]", end="")
            if current_requirements:
                print(f" [要求: {current_requirements[:30]}...]", end="")
            print()
            
            user_input = input("\n请输入（文本/命令）> ").strip()
            
            if not user_input:
                continue
            
            # 处理命令
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 再见！")
                break
            
            if user_input.lower() == 'help':
                print("\n帮助信息：")
                print("  - 直接输入英文文本即可翻译")
                print("  - 'style:rigorous' - 切换到严谨风格（保持专业术语）")
                print("  - 'style:popular' - 切换到通俗风格（减少专业术语）")
                print("  - 'req:你的要求' - 设置额外翻译要求")
                print("  - 'clear' - 清除当前要求")
                print("  - 'quit' - 退出程序")
                continue
            
            if user_input.lower() == 'clear':
                current_requirements = None
                print("  √ 已清除额外要求")
                continue
            
            if user_input.startswith('style:'):
                style_value = user_input[6:].strip().lower()
                if style_value in ['rigorous', '严谨', 'r']:
                    current_style = "rigorous"
                    print("  √ 已切换到严谨风格（保持专业术语）")
                elif style_value in ['popular', '通俗', 'p']:
                    current_style = "popular"
                    print("  √ 已切换到通俗风格（减少专业术语）")
                else:
                    print("  [WARNING] 无效的风格，请使用 'rigorous' 或 'popular'")
                continue
            
            if user_input.startswith('req:'):
                current_requirements = user_input[4:].strip()
                print(f"  √ 已设置额外要求: {current_requirements}")
                continue
            
            # 执行翻译
            print(f"\n  正在翻译（风格: {style_display}）...")
            result = translate_with_style(
                source_text=user_input,
                translation_style=current_style,
                user_requirements=current_requirements
            )
            
            if "error" not in result:
                print(f"\n  √ 翻译完成！")
                print(f"\n【原文】")
                print(result["source_text"])
                print(f"\n【译文】")
                print(result["translation"])
                
                # 保存结果
                saved_path = save_translation_result(result)
                if saved_path:
                    print(f"\n  已保存至: {saved_path}")
                    translation_count += 1
            else:
                print(f"\n  × 翻译失败: {result.get('error')}")
        
        except KeyboardInterrupt:
            print("\n\n👋 再见！")
            break
        except Exception as e:
            print(f"\n  × 发生错误: {e}")
            import traceback
            traceback.print_exc()
    
    if translation_count > 0:
        print(f"\n本次会话共完成 {translation_count} 次翻译")


if __name__ == "__main__":
    interactive_translate_loop()

