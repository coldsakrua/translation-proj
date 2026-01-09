#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速开始示例 - T-Ragx API 翻译

最简单的使用方式，复制此文件并根据需要修改
"""

import os
import t_ragx

# ==================== 配置 ====================
# 请修改以下配置

# OpenRouter API 配置
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")  # 替换为你的 OpenRouter API Key，或设置环境变量
API_BASE_URL = "https://openrouter.ai/api/v1"  # OpenRouter API 地址
MODEL_NAME = "qwen/qwen3-4b:free"  # OpenRouter 模型名称
# 可选模型: "openai/gpt-3.5-turbo", "openai/gpt-4", "qwen/qwen3-4b:free", "meta-llama/llama-3.2-3b-instruct:free" 等
# 查看所有可用模型: https://openrouter.ai/models

# OpenRouter 可选配置（用于统计和排名）
# 如果不需要，可以保持为空字典 {}
OPENROUTER_EXTRA_HEADERS = {
    # "HTTP-Referer": "https://your-site.com",  # 可选：你的网站 URL
    # "X-Title": "Your Site Name",  # 可选：你的网站名称
}
OPENROUTER_EXTRA_BODY = {}  # 可选：额外的请求体参数

# ==================== 初始化 ====================

print("🚀 初始化翻译系统...")

# 1. 初始化输入处理器
input_processor = t_ragx.processors.ElasticInputProcessor()
input_processor.load_general_glossary()  # 加载词汇表（可选）
input_processor.load_general_translation(
    elastic_index="general_translation_memory",
    elasticsearch_host=["https://t-ragx-fossil.rayliu.ca", "https://t-ragx-fossil2.rayliu.ca"]
)

# 2. 初始化 OpenRouter API 模型
from urllib.parse import urlparse
parsed_url = urlparse(API_BASE_URL)
api_model = t_ragx.models.OpenAIModel(
    host=parsed_url.hostname,
    port=parsed_url.port or (443 if parsed_url.scheme == "https" else 80),
    endpoint=parsed_url.path or "/v1",
    model=MODEL_NAME,
    protocol=parsed_url.scheme or "https",
    api_key=OPENROUTER_API_KEY
)

# 3. 创建翻译器
translator = t_ragx.TRagx([api_model], input_processor=input_processor)

print("✅ 初始化完成！\n")

# ==================== 使用示例 ====================

# 示例1: 中文 → 英文
print("=" * 60)
print("示例1: 中文 → 英文")
print("=" * 60)
chinese_text = "人工智能是未来科技发展的重要方向。"
result = translator.batch_translate(
    [chinese_text],
    source_lang_code='zh',
    target_lang_code='en',
    memory_search_args={'top_k': 3},
    generation_args=[{
        'max_tokens': 2048,
        'temperature': 0.7,
        'extra_headers': OPENROUTER_EXTRA_HEADERS,  # OpenRouter 额外请求头（可选）
        'extra_body': OPENROUTER_EXTRA_BODY  # OpenRouter 额外请求体（可选）
    }]
)
print(f"原文: {chinese_text}")
print(f"译文: {result[0]}\n")

# 示例2: 英文 → 中文
print("=" * 60)
print("示例2: 英文 → 中文")
print("=" * 60)
english_text = "Artificial intelligence is an important direction for future technological development."
result = translator.batch_translate(
    [english_text],
    source_lang_code='en',
    target_lang_code='zh',
    memory_search_args={'top_k': 3},
    generation_args=[{
        'max_tokens': 2048,
        'temperature': 0.7,
        'extra_headers': OPENROUTER_EXTRA_HEADERS,
        'extra_body': OPENROUTER_EXTRA_BODY
    }]
)
print(f"原文: {english_text}")
print(f"译文: {result[0]}\n")

# 示例3: 批量翻译
print("=" * 60)
print("示例3: 批量翻译（文档级上下文）")
print("=" * 60)
chinese_sentences = [
    "机器学习是人工智能的核心技术。",
    "它使计算机能够从数据中学习。",
    "深度学习是机器学习的一个分支。"
]
# 获取前文上下文
pre_text_list = t_ragx.utils.helper.get_preceding_text(chinese_sentences, max_sent=3)
results = translator.batch_translate(
    chinese_sentences,
    pre_text_list=pre_text_list,
    source_lang_code='zh',
    target_lang_code='en',
    memory_search_args={'top_k': 3},
    generation_args=[{
        'max_tokens': 2048,
        'temperature': 0.7,
        'extra_headers': OPENROUTER_EXTRA_HEADERS,
        'extra_body': OPENROUTER_EXTRA_BODY
    }]
)
print("批量翻译结果:")
for i, (src, tgt) in enumerate(zip(chinese_sentences, results), 1):
    print(f"{i}. {src}")
    print(f"   → {tgt}\n")

print("=" * 60)
print("完成！")
print("=" * 60)

