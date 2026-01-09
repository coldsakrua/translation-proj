#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基于 API 调用的 T-Ragx 翻译 RAG 系统
适用于算力不足的电脑，通过 API 调用远程模型进行翻译

支持：
- OpenAI API（官方或兼容 API）
- 中英文互译
- RAG 增强翻译（使用 Elasticsearch 翻译记忆库）
"""

import os
import logging
import t_ragx

# 配置日志
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("elasticsearch").setLevel(logging.WARNING)

# ==================== 配置区域 ====================

# 1. OpenAI API 配置（支持 OpenAI 官方 API 或兼容 API）
# 方式1: 使用 OpenAI 官方 API（推荐）
OPENAI_CONFIG = {
    "base_url": "https://api.openai.com/v1",
    "api_key": os.getenv("OPENAI_API_KEY", ""),  # 从环境变量读取，或直接填写
    "model": "gpt-3.5-turbo",  # 可选: "gpt-4", "gpt-4-turbo", "gpt-4o" 等
}

# 方式2: 使用国内 API 服务（如 DeepSeek、Moonshot 等）
# OPENAI_CONFIG = {
#     "base_url": "https://api.deepseek.com/v1",  # DeepSeek API
#     "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
#     "model": "deepseek-chat",
# }

# 方式3: 使用本地或远程的兼容 API（如 Ollama 的 OpenAI 兼容接口）
# OPENAI_CONFIG = {
#     "base_url": "http://localhost:11434/v1",  # Ollama 的 OpenAI 兼容接口
#     "api_key": "ollama",  # Ollama 不需要真实 key
#     "model": "qwen2.5:7b",  # 你的模型名称
# }

# 2. Elasticsearch 配置（翻译记忆库）
ES_CONFIG = {
    # 方式1: 使用项目提供的远程 ES 服务（只读）
    "hosts": ["https://t-ragx-fossil.rayliu.ca", "https://t-ragx-fossil2.rayliu.ca"],
    "index": "general_translation_memory",
    
    # 方式2: 使用本地 Elasticsearch
    # "hosts": ["http://localhost:9200"],
    # "index": "zh_en_translation_memory",  # 你的本地索引名
}

# 3. 翻译配置
TRANSLATION_CONFIG = {
    "memory_search_top_k": 3,  # 检索的翻译记忆数量
    "max_tokens": 2048,  # 最大生成 token 数
    "temperature": 0.7,  # 温度参数（控制随机性）
}

# ==================== 初始化函数 ====================

def init_translator():
    """
    初始化翻译器
    返回配置好的 T-Ragx 翻译器实例
    """
    print("🚀 正在初始化 T-Ragx 翻译系统...")
    
    # 1. 初始化输入处理器（处理翻译记忆和词汇表检索）
    print("📚 初始化输入处理器...")
    input_processor = t_ragx.processors.ElasticInputProcessor()
    
    # 加载通用词汇表（可选）
    try:
        input_processor.load_general_glossary()
        print("✅ 通用词汇表加载成功")
    except Exception as e:
        print(f"⚠️ 词汇表加载失败（可选）: {e}")
    
    # 加载翻译记忆库
    try:
        input_processor.load_general_translation(
            elastic_index=ES_CONFIG["index"],
            elasticsearch_host=ES_CONFIG["hosts"]
        )
        print("✅ 翻译记忆库连接成功")
    except Exception as e:
        print(f"❌ 翻译记忆库连接失败: {e}")
        print("   提示：如果使用本地 ES，请确保 Elasticsearch 已启动")
        raise
    
    # 2. 初始化 API 模型
    print("🤖 初始化 API 模型...")
    
    # 解析 base_url 获取 host, port, endpoint
    from urllib.parse import urlparse
    parsed_url = urlparse(OPENAI_CONFIG["base_url"])
    
    host = parsed_url.hostname or "api.openai.com"
    # 如果没有指定端口，根据协议使用默认端口
    if parsed_url.port:
        port = parsed_url.port
    else:
        port = 443 if parsed_url.scheme == "https" else 80
    endpoint = parsed_url.path if parsed_url.path else "/v1"
    protocol = parsed_url.scheme if parsed_url.scheme else "https"
    
    print(f"   连接: {protocol}://{host}:{port}{endpoint}")
    print(f"   模型: {OPENAI_CONFIG['model']}")
    
    # 创建 OpenAI 兼容模型
    api_model = t_ragx.models.OpenAIModel(
        host=host,
        port=port,
        endpoint=endpoint,
        model=OPENAI_CONFIG["model"],
        protocol=protocol,
        api_key=OPENAI_CONFIG["api_key"]
    )
    print(f"✅ API 模型初始化成功: {OPENAI_CONFIG['model']}")
    
    # 3. 创建 T-Ragx 翻译器
    translator = t_ragx.TRagx([api_model], input_processor=input_processor)
    print("✅ T-Ragx 翻译器初始化完成！\n")
    
    return translator


# ==================== 翻译函数 ====================

def translate_text(translator, text, source_lang='zh', target_lang='en'):
    """
    翻译单个文本
    
    Args:
        translator: T-Ragx 翻译器实例
        text: 要翻译的文本
        source_lang: 源语言代码 ('zh' 中文, 'en' 英文)
        target_lang: 目标语言代码 ('zh' 中文, 'en' 英文)
    
    Returns:
        翻译结果字符串
    """
    lang_code_map = {
        'zh': 'zh',
        'en': 'en',
        'chinese': 'zh',
        'english': 'en',
        '中文': 'zh',
        '英文': 'en'
    }
    
    source_code = lang_code_map.get(source_lang.lower(), source_lang)
    target_code = lang_code_map.get(target_lang.lower(), target_lang)
    
    print(f"📝 翻译中: {text[:50]}...")
    print(f"   方向: {source_code} → {target_code}")
    
    try:
        results = translator.batch_translate(
            [text],
            source_lang_code=source_code,
            target_lang_code=target_code,
            memory_search_args={'top_k': TRANSLATION_CONFIG["memory_search_top_k"]},
            generation_args=[{
                'max_tokens': TRANSLATION_CONFIG["max_tokens"],
                'temperature': TRANSLATION_CONFIG["temperature"]
            }]
        )
        
        translation = results[0] if results else ""
        print(f"✅ 翻译完成\n")
        return translation
    
    except Exception as e:
        print(f"❌ 翻译失败: {e}\n")
        raise


def translate_batch(translator, texts, source_lang='zh', target_lang='en', 
                    use_context=True):
    """
    批量翻译文本列表（支持文档级上下文）
    
    Args:
        translator: T-Ragx 翻译器实例
        texts: 要翻译的文本列表
        source_lang: 源语言代码
        target_lang: 目标语言代码
        use_context: 是否使用前文上下文（文档级翻译）
    
    Returns:
        翻译结果列表
    """
    lang_code_map = {
        'zh': 'zh',
        'en': 'en',
        'chinese': 'zh',
        'english': 'en',
        '中文': 'zh',
        '英文': 'en'
    }
    
    source_code = lang_code_map.get(source_lang.lower(), source_lang)
    target_code = lang_code_map.get(target_lang.lower(), target_lang)
    
    print(f"📝 批量翻译 {len(texts)} 条文本")
    print(f"   方向: {source_code} → {target_code}")
    print(f"   使用上下文: {use_context}\n")
    
    # 获取前文上下文（用于文档级翻译）
    pre_text_list = None
    if use_context:
        pre_text_list = t_ragx.utils.helper.get_preceding_text(texts, max_sent=3)
    
    try:
        results = translator.batch_translate(
            texts,
            pre_text_list=pre_text_list,
            source_lang_code=source_code,
            target_lang_code=target_code,
            memory_search_args={'top_k': TRANSLATION_CONFIG["memory_search_top_k"]},
            generation_args=[{
                'max_tokens': TRANSLATION_CONFIG["max_tokens"],
                'temperature': TRANSLATION_CONFIG["temperature"]
            }]
        )
        
        print(f"✅ 批量翻译完成\n")
        return results
    
    except Exception as e:
        print(f"❌ 翻译失败: {e}\n")
        raise


# ==================== 主程序 ====================

def main():
    """主函数 - 演示如何使用"""
    
    # 初始化翻译器
    translator = init_translator()
    
    print("=" * 60)
    print("T-Ragx API 翻译系统已就绪！")
    print("=" * 60)
    print()
    
    # 示例 1: 单句翻译 - 中文到英文
    print("【示例 1】中文 → 英文")
    chinese_text = "人工智能是计算机科学的一个分支，它试图理解智能的实质，并生产出一种新的能以人类智能相似的方式做出反应的智能机器。"
    english_result = translate_text(translator, chinese_text, 'zh', 'en')
    print(f"原文: {chinese_text}")
    print(f"译文: {english_result}")
    print()
    
    # 示例 2: 单句翻译 - 英文到中文
    print("【示例 2】英文 → 中文")
    english_text = "Artificial intelligence is a branch of computer science that attempts to understand the essence of intelligence and produce a new kind of intelligent machine that can react in a way similar to human intelligence."
    chinese_result = translate_text(translator, english_text, 'en', 'zh')
    print(f"原文: {english_text}")
    print(f"译文: {chinese_result}")
    print()
    
    # 示例 3: 批量翻译（文档级）
    print("【示例 3】批量翻译（文档级上下文）")
    chinese_sentences = [
        "机器学习是人工智能的核心技术之一。",
        "它使计算机能够从数据中学习，而无需明确编程。",
        "深度学习是机器学习的一个子领域。",
        "它使用神经网络来模拟人脑的工作方式。"
    ]
    english_results = translate_batch(translator, chinese_sentences, 'zh', 'en', use_context=True)
    
    print("原文与译文对照:")
    for i, (src, tgt) in enumerate(zip(chinese_sentences, english_results), 1):
        print(f"{i}. 原文: {src}")
        print(f"   译文: {tgt}")
        print()
    
    print("=" * 60)
    print("演示完成！")
    print("=" * 60)


# ==================== 交互式使用 ====================

def interactive_mode():
    """交互式翻译模式"""
    translator = init_translator()
    
    print("=" * 60)
    print("T-Ragx 交互式翻译模式")
    print("输入 'quit' 或 'exit' 退出")
    print("输入格式: <源语言> <目标语言> <文本>")
    print("例如: zh en 你好世界")
    print("=" * 60)
    print()
    
    while True:
        try:
            user_input = input("请输入翻译指令: ").strip()
            
            if user_input.lower() in ['quit', 'exit', '退出']:
                print("再见！")
                break
            
            if not user_input:
                continue
            
            # 解析输入
            parts = user_input.split(' ', 2)
            if len(parts) < 3:
                print("❌ 格式错误，请使用: <源语言> <目标语言> <文本>")
                continue
            
            source_lang, target_lang, text = parts
            
            # 翻译
            result = translate_text(translator, text, source_lang, target_lang)
            print(f"翻译结果: {result}\n")
        
        except KeyboardInterrupt:
            print("\n\n再见！")
            break
        except Exception as e:
            print(f"❌ 错误: {e}\n")


if __name__ == "__main__":
    import sys
    
    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        # 交互式模式
        interactive_mode()
    else:
        # 演示模式
        main()

