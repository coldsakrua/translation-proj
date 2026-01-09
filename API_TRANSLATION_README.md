# T-Ragx API 翻译系统使用指南

这是一个基于 API 调用的 T-Ragx 翻译 RAG 系统，适用于算力不足的电脑。通过调用远程 API 服务进行翻译，无需本地运行大模型。

## 功能特点

- ✅ **无需本地算力**：通过 API 调用远程模型
- ✅ **RAG 增强翻译**：使用 Elasticsearch 翻译记忆库提供上下文
- ✅ **中英文互译**：支持中文↔英文双向翻译
- ✅ **文档级翻译**：支持使用前文上下文进行连贯翻译
- ✅ **批量翻译**：支持批量处理多个句子

## 安装依赖

```bash
# 激活 conda 环境（如果使用）
conda activate t-ragx

# 安装依赖（如果还没安装）
pip install t-ragx openai
```

## 配置说明

### 1. API 配置

编辑 `api_translation_rag.py` 中的 `OPENAI_CONFIG`：

#### 使用 OpenAI 官方 API

```python
OPENAI_CONFIG = {
    "base_url": "https://api.openai.com/v1",
    "api_key": "sk-your-api-key-here",  # 或从环境变量读取
    "model": "gpt-3.5-turbo",  # 或 "gpt-4", "gpt-4-turbo"
}
```

**获取 API Key**：
- 访问 https://platform.openai.com/api-keys
- 创建新的 API Key
- 设置环境变量：`export OPENAI_API_KEY=sk-xxx`

#### 使用国内 API 服务

**DeepSeek**：
```python
OPENAI_CONFIG = {
    "base_url": "https://api.deepseek.com/v1",
    "api_key": "your-deepseek-key",
    "model": "deepseek-chat",
}
```

**Moonshot**：
```python
OPENAI_CONFIG = {
    "base_url": "https://api.moonshot.cn/v1",
    "api_key": "your-moonshot-key",
    "model": "moonshot-v1-8k",
}
```

**其他兼容 OpenAI API 的服务**：
```python
OPENAI_CONFIG = {
    "base_url": "https://your-api-endpoint.com/v1",
    "api_key": "your-api-key",
    "model": "your-model-name",
}
```

### 2. Elasticsearch 配置

#### 使用远程 ES 服务（推荐，无需配置）

项目提供了免费的远程 ES 服务，直接使用即可：

```python
ES_CONFIG = {
    "hosts": ["https://t-ragx-fossil.rayliu.ca", "https://t-ragx-fossil2.rayliu.ca"],
    "index": "general_translation_memory",
}
```

#### 使用本地 Elasticsearch

如果已搭建本地 ES：

```python
ES_CONFIG = {
    "hosts": ["http://localhost:9200"],
    "index": "zh_en_translation_memory",
}
```

## 使用方法

### 方法1: 直接运行演示

```bash
python api_translation_rag.py
```

这会运行预设的示例，展示：
- 中文→英文翻译
- 英文→中文翻译
- 批量翻译（文档级上下文）

### 方法2: 交互式模式

```bash
python api_translation_rag.py interactive
```

然后按提示输入：
```
请输入翻译指令: zh en 人工智能是计算机科学的一个分支
```

格式：`<源语言> <目标语言> <文本>`

### 方法3: 在代码中使用

```python
from api_translation_rag import init_translator, translate_text, translate_batch

# 初始化翻译器
translator = init_translator()

# 单句翻译
result = translate_text(translator, "你好世界", 'zh', 'en')
print(result)

# 批量翻译
texts = ["第一句话", "第二句话", "第三句话"]
results = translate_batch(translator, texts, 'zh', 'en', use_context=True)
for text, result in zip(texts, results):
    print(f"{text} -> {result}")
```

## 完整示例

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
from api_translation_rag import init_translator, translate_text

# 初始化
translator = init_translator()

# 翻译中文到英文
chinese = "机器学习是人工智能的核心技术之一。"
english = translate_text(translator, chinese, 'zh', 'en')
print(f"中文: {chinese}")
print(f"英文: {english}")

# 翻译英文到中文
english = "Machine learning is one of the core technologies of artificial intelligence."
chinese = translate_text(translator, english, 'en', 'zh')
print(f"英文: {english}")
print(f"中文: {chinese}")
```

## 常见问题

### 1. API Key 错误

**错误**：`Invalid API Key`

**解决**：
- 检查 API Key 是否正确
- 确认 API Key 有足够的余额
- 使用环境变量：`export OPENAI_API_KEY=sk-xxx`

### 2. Elasticsearch 连接失败

**错误**：`无法连接到Elasticsearch`

**解决**：
- 如果使用远程 ES，检查网络连接
- 如果使用本地 ES，确保 Elasticsearch 已启动：
  ```bash
  # Windows
  cd ESBuilderScripts
  start_es.bat
  
  # Linux/Mac
  docker run -d -p 9200:9200 -e "discovery.type=single-node" elasticsearch:7.9.1
  ```

### 3. 翻译结果不理想

**优化建议**：
- 调整 `temperature` 参数（0.7-1.0 之间）
- 增加 `memory_search_top_k`（3-5）
- 使用更好的模型（如 gpt-4）

### 4. API 调用速度慢

**优化建议**：
- 使用批量翻译而不是逐句翻译
- 选择响应更快的 API 服务
- 减少 `memory_search_top_k` 数量

## 成本估算

### OpenAI API 成本（参考）

- **gpt-3.5-turbo**: ~$0.002/1K tokens（输入+输出）
- **gpt-4**: ~$0.03/1K tokens（输入）+ $0.06/1K tokens（输出）

**示例**：翻译 1000 个中文字符（约 500 tokens）
- gpt-3.5-turbo: 约 $0.001-0.002
- gpt-4: 约 $0.02-0.03

### 国内 API 服务

通常比 OpenAI 便宜，具体价格请查看各服务商官网。

## 注意事项

1. **API 费用**：使用 API 会产生费用，请注意控制使用量
2. **网络要求**：需要稳定的网络连接
3. **数据隐私**：使用第三方 API 时，文本会发送到服务商，注意隐私保护
4. **速率限制**：大多数 API 服务都有速率限制，批量翻译时注意控制频率

## 技术支持

如有问题，请参考：
- T-Ragx 官方文档：https://github.com/rayliuca/T-Ragx
- OpenAI API 文档：https://platform.openai.com/docs

