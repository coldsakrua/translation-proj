#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API 翻译配置示例文件
复制此文件并根据你的实际情况修改配置
"""

import os

# ==================== OpenAI API 配置 ====================

# 方式1: 使用 OpenAI 官方 API
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

# 方式3: 使用本地 Ollama（如果本地有 Ollama 服务）
# OPENAI_CONFIG = {
#     "base_url": "http://localhost:11434/v1",  # Ollama 的 OpenAI 兼容接口
#     "api_key": "ollama",  # Ollama 不需要真实 key
#     "model": "qwen2.5:7b",  # 你的模型名称
# }

# 方式4: 使用其他兼容 OpenAI API 的服务
# OPENAI_CONFIG = {
#     "base_url": "https://your-api-endpoint.com/v1",
#     "api_key": "your-api-key",
#     "model": "your-model-name",
# }

# ==================== Elasticsearch 配置 ====================

# 方式1: 使用项目提供的远程 ES 服务（只读，无需配置）
ES_CONFIG = {
    "hosts": ["https://t-ragx-fossil.rayliu.ca", "https://t-ragx-fossil2.rayliu.ca"],
    "index": "general_translation_memory",
}

# 方式2: 使用本地 Elasticsearch（需要先启动 ES）
# ES_CONFIG = {
#     "hosts": ["http://localhost:9200"],
#     "index": "zh_en_translation_memory",  # 你的本地索引名
# }

# 方式3: 使用自建远程 Elasticsearch
# ES_CONFIG = {
#     "hosts": ["https://your-es-server.com:9200"],
#     "index": "your_index_name",
#     # 如果需要认证
#     # "auth": ("username", "password"),
# }

# ==================== 翻译参数配置 ====================

TRANSLATION_CONFIG = {
    "memory_search_top_k": 3,  # 从翻译记忆库检索的相似翻译数量（建议 3-5）
    "max_tokens": 2048,  # 最大生成 token 数
    "temperature": 0.7,  # 温度参数（0-2，越高越随机，建议 0.7-1.0）
}

