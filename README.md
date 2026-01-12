# T-Ragx 翻译系统

基于 RAG（检索增强生成）和 LangGraph 多Agent工作流的智能翻译系统，专为AI论文翻译设计。

## 📋 目录

- [功能特点](#功能特点)
- [系统架构](#系统架构)
- [安装与配置](#安装与配置)
- [快速开始](#快速开始)
- [使用指南](#使用指南)
- [工作流程](#工作流程)
- [文件结构](#文件结构)
- [高级功能](#高级功能)

## ✨ 功能特点

### 核心功能

- **多Agent工作流**：基于 LangGraph 的翻译工作流，包含风格分析、术语识别、翻译生成、质量评估等节点
- **RAG增强翻译**：使用 Elasticsearch 检索翻译记忆和术语库，提供上下文增强
- **TEaR迭代优化**：Translate（翻译）→ Estimate（评估）→ Refine（修正）循环，自动提升翻译质量
- **术语一致性管理**：自动识别术语，支持人工审查，确保全书术语统一
- **章节级翻译**：支持长文档分章节翻译，保持上下文连贯性
- **质量评分系统**：自动评估翻译质量（0-10分），支持回译一致性、术语一致性等多维度评估

### 人工介入功能

- **术语审查**：批量显示所有术语，支持按ID修改，超时自动接受
- **章节翻译审查**：审查章节翻译质量，支持反馈意见和重新翻译
- **超时机制**：所有人工介入步骤支持超时自动跳过，适合批量处理

### 辅助功能

- **交互式翻译**：对话式翻译工具，支持严谨/通俗两种翻译风格
- **翻译记忆导入**：支持导入已有论文翻译对到RAG系统
- **质量评分导出**：单独保存质量评分到JSON文件，方便分析
- **自动模式**：支持禁用人工审查，全自动翻译流程

## 🏗️ 系统架构

### 工作流节点

```
START
  ↓
[分析风格] → [提取术语] → [搜索术语] → [翻译生成]
                                              ↓
                                          [质量评估]
                                              ↓
                                    ┌─────────┴─────────┐
                                    ↓                   ↓
                               [质量通过]          [质量不足]
                                    ↓                   ↓
                              [持久化保存]        [修正翻译]
                                                      ↓
                                                  [重新评估]
                                                      ↓
                                    ┌─────────────────┘
                                    ↓
                              [持久化保存]
                                    ↓
                                   END
```

### 核心组件

- **TranslationState**：LangGraph状态，包含原文、译文、术语表、质量评分等
- **RAG检索器**：Elasticsearch检索翻译记忆和术语
- **术语管理器**：术语识别、标准化、一致性检查
- **质量评估器**：多维度翻译质量评估
- **人工审查模块**：术语和翻译质量的人工审查接口

## 📦 安装与配置

### 环境要求

- Python 3.8+
- Elasticsearch 7.x 或 8.x（用于RAG检索）
- 推荐使用 conda/mamba 管理环境

### 安装步骤

1. **克隆仓库**
```bash
git clone <repository-url>
cd translation-proj
```

2. **安装依赖**
```bash
# 使用conda（推荐）
conda env create -f environment.yml
conda activate t-ragx

# 或使用pip
pip install -r requirements.txt
```

3. **配置Elasticsearch**

确保Elasticsearch服务正在运行：
```bash
# 检查ES是否运行
curl http://localhost:9200
```

如果需要中文分词，安装IK分词插件：
```bash
# 在ES安装目录执行
bin/elasticsearch-plugin install https://github.com/medcl/elasticsearch-analysis-ik/releases/download/v8.x.x/elasticsearch-analysis-ik-8.x.x.zip
```

4. **配置LLM**

编辑 `try/core/get_llm.py` 配置你的LLM API：
- OpenAI API
- 其他兼容OpenAI API的服务（DeepSeek、Moonshot等）

## 🚀 快速开始

### 1. 书籍翻译（主功能）

```bash
cd try

# 启用人工审查（默认）
python main.py --paper-id vgg

# 禁用人工审查（自动模式）
python main.py --paper-id vgg --no-human-review

# 指定JSON文件路径
python main.py --json-path D:/hw/translation-proj/data/vgg_en.json --paper-id vgg
```

**参数说明**：
- `--paper-id`: 论文ID（默认: vgg）
- `--json-path`: JSON文件路径（可选，默认使用 `data/{paper-id}_en.json`）
- `--no-human-review`: 禁用人工审查，自动接受所有术语和翻译

### 2. 交互式翻译

```bash
cd try
python interactive_translate.py
```

**功能**：
- 输入文本进行即时翻译
- 选择翻译风格：严谨（rigorous）或通俗（popular）
- 添加自定义要求
- 自动保存翻译结果

**命令**：
- `help`: 查看帮助
- `style rigorous`: 切换到严谨风格
- `style popular`: 切换到通俗风格
- `requirements <要求>`: 设置额外要求
- `clear`: 清除额外要求
- `quit`: 退出

### 3. 导入翻译对到RAG系统

```bash
cd try

# 导入单个文件对
python rag/import_translation_pairs.py --en data/vgg_en.json --zh data/vgg_ch.json

# 导入所有翻译对
python rag/import_translation_pairs.py --all

# 查看已导入的翻译对
python rag/import_translation_pairs.py --view
```

**或使用便捷脚本**：
```bash
python scripts/import_paper_translations.py
```

## 📖 使用指南

### 书籍翻译流程

#### 1. 准备数据

确保 `data/` 目录下有对应的JSON文件：
- `{paper_id}_en.json`: 英文原文（章节列表格式）
- `{paper_id}_ch.json`: 中文译文（可选，用于导入RAG）

JSON格式示例：
```json
[
  {
    "title": "Chapter 1",
    "content": "Chapter content here...",
    "level": 1
  },
  ...
]
```

#### 2. 运行翻译

```bash
python main.py --paper-id vgg
```

#### 3. 工作流程

**Phase 1: 自动翻译所有chunks**
- 系统自动将章节分割为chunks
- 对每个chunk执行完整翻译流程
- 生成翻译和质量评分

**Phase 2: 术语审查（如果启用人工审查）**
- 收集整个章节的术语
- 显示术语列表，支持按ID修改
- 超时时间：术语数 × 10秒
- 每次回到界面时时间刷新

**Phase 3: 生成章节摘要**
- 基于翻译结果生成章节摘要
- 用于后续章节的上下文参考

**Phase 4: 章节翻译质量审查（如果启用人工审查）**
- 显示翻译统计和质量评分
- 用户选择接受/不接受/跳过
- 如果不接受，可输入修改意见（3分钟超时）
- 根据反馈自动重新翻译（最多3次）

#### 4. 输出结果

翻译结果保存在 `output/{book_id}/chapter_{id}/` 目录：
- `chunk_{id:03d}.json`: 每个chunk的翻译结果
- `quality_scores.json`: 质量评分汇总
- `chapter_summaries.json`: 章节摘要
- `translation_memory.json`: 翻译记忆库

### 交互式翻译使用

1. **启动交互式翻译**
```bash
python interactive_translate.py
```

2. **输入文本**
```
请输入（文本/命令）> This is a test sentence.
```

3. **选择风格**
```
请输入（文本/命令）> style rigorous  # 严谨风格
请输入（文本/命令）> style popular   # 通俗风格
```

4. **添加要求**
```
请输入（文本/命令）> requirements 请使用更正式的学术表达
```

5. **查看结果**
翻译完成后会自动显示，并询问是否保存。

### RAG系统管理

#### 导入翻译对

```bash
# 方式1：导入指定文件对
python rag/import_translation_pairs.py --en data/vgg_en.json --zh data/vgg_ch.json

# 方式2：批量导入所有文件对
python rag/import_translation_pairs.py --all

# 方式3：导入并查看
python rag/import_translation_pairs.py --en data/vgg_en.json --zh data/vgg_ch.json --view
```

导入的翻译对会：
- 保存到 Elasticsearch 用于RAG检索
- 保存JSON文件到 `output/imported_translations/` 目录
- 生成导入汇总文件

#### 查看已导入的翻译对

```bash
python rag/import_translation_pairs.py --view
```

#### 导出RAG数据

RAG数据会在术语审查后自动备份到 `output/rag_backups/` 目录。

## 🔄 工作流程

### 完整翻译流程

```
1. 加载章节内容
   ↓
2. 加载全局术语表和上下文
   ↓
3. 分割章节为chunks
   ↓
4. 【Phase 1】自动翻译所有chunks
   ├─ 分析风格
   ├─ 提取术语
   ├─ 搜索术语（RAG）
   ├─ 翻译生成
   ├─ 质量评估（TEaR）
   └─ 保存结果
   ↓
5. 【Phase 2】术语审查（可选）
   ├─ 收集章节术语
   ├─ 人工审查术语
   └─ 更新chunk文件
   ↓
6. 【Phase 3】生成章节摘要
   ↓
7. 【Phase 4】章节翻译质量审查（可选）
   ├─ 显示翻译统计
   ├─ 人工审查
   ├─ 如果不接受 → 重新翻译（最多3次）
   └─ 保存质量评分
   ↓
8. 完成
```

### TEaR迭代优化流程

```
翻译生成
   ↓
质量评估
   ├─ 回译一致性
   ├─ 术语一致性
   ├─ 长度比例
   └─ 综合评分
   ↓
评分 >= 7?
   ├─ 是 → 保存结果
   └─ 否 → 修正翻译
              ↓
        重新评估
              ↓
        循环（最多3次）
```

## 📁 文件结构

```
translation-proj/
├── try/                          # 主代码目录
│   ├── main.py                   # 主入口：书籍翻译
│   ├── interactive_translate.py  # 交互式翻译入口
│   ├── task.py                   # 翻译任务处理器
│   ├── core/                     # 核心模块
│   │   ├── graph.py              # LangGraph工作流定义
│   │   ├── nodes.py              # 工作流节点实现
│   │   ├── get_llm.py            # LLM配置
│   │   └── ...
│   ├── utils/                    # 工具模块
│   │   ├── human.py              # 人工审查功能
│   │   ├── interactive_translator.py  # 交互式翻译
│   │   ├── memory_storage.py     # 翻译记忆存储
│   │   ├── glossary_storage.py  # 术语存储
│   │   ├── translation_evaluator.py  # 质量评估
│   │   └── ...
│   ├── rag/                      # RAG模块
│   │   ├── es_retriever.py       # Elasticsearch检索
│   │   └── import_translation_pairs.py  # 导入翻译对
│   ├── scripts/                  # 脚本
│   │   └── import_paper_translations.py  # 批量导入脚本
│   └── output/                   # 输出目录
│       ├── {book_id}/            # 书籍输出
│       │   ├── chapter_{id}/     # 章节输出
│       │   │   ├── chunk_*.json  # chunk翻译结果
│       │   │   └── quality_scores.json  # 质量评分
│       │   ├── chapter_summaries.json   # 章节摘要
│       │   └── translation_memory.json  # 翻译记忆
│       ├── imported_translations/  # 导入的翻译对
│       └── rag_backups/          # RAG数据备份
├── data/                         # 数据目录
│   ├── {paper_id}_en.json        # 英文原文
│   └── {paper_id}_ch.json        # 中文译文（可选）
└── README.md                     # 本文档
```

## 🎯 高级功能

### 1. 术语审查界面

术语审查采用批量显示模式：
- 一次性显示所有术语列表
- 输入术语ID进行修改
- 输入 `d{ID}` 删除术语
- 输入 `q` 完成审查
- 每次回到界面时时间刷新（术语数 × 10秒）

### 2. 重新翻译机制

当章节翻译不被接受时：
- 用户输入修改意见（3分钟超时）
- 系统根据反馈重新翻译所有chunks
- 最多重试3次
- 每次重试都会使用反馈意见改进翻译

### 3. 质量评分系统

质量评分包含多个维度：
- **回译一致性**：回译后与原文的相似度
- **术语一致性**：术语使用的准确性
- **长度比例**：中英文长度比合理性
- **综合评分**：0-10分

评分保存在：
- `chunk_*.json` 中的 `quality_score` 字段
- `quality_scores.json` 汇总文件

### 4. 自动模式

使用 `--no-human-review` 参数：
- 自动接受所有术语
- 自动接受章节翻译
- 跳过所有人工介入步骤
- 适合批量处理和自动化场景

### 5. 翻译风格选择

交互式翻译支持两种风格：
- **严谨风格（rigorous）**：保持专业术语，适合AI论文
- **通俗风格（popular）**：减少专业术语，更易理解

## 📊 输出文件说明

### Chunk文件格式

```json
{
  "chunk_id": 0,
  "source_text": "原文...",
  "translation": "译文...",
  "quality_score": 8.5,
  "glossary": [...],
  "refinement_history": [...],
  "revision_count": 1
}
```

### 质量评分文件格式

```json
{
  "book_id": "vgg",
  "chapter_id": 0,
  "reviewed_at": "2024-01-01T12:00:00",
  "statistics": {
    "total_chunks": 5,
    "average_score": 8.5,
    "min_score": 7.0,
    "max_score": 9.5
  },
  "chunk_scores": [...]
}
```

## 🔧 配置说明

### LLM配置

编辑 `try/core/get_llm.py` 配置LLM：

```python
# OpenAI API
llm = ChatOpenAI(
    model="gpt-4",
    temperature=0.3,
    api_key="your-api-key"
)

# 或其他兼容OpenAI API的服务
```

### Elasticsearch配置

编辑 `try/rag/es_retriever.py`：

```python
es = Elasticsearch("http://localhost:9200")
INDEX_NAME = "translation_memory"
```

## 📝 注意事项

1. **Elasticsearch服务**：确保ES服务正在运行，否则RAG功能不可用
2. **超时设置**：术语审查超时为术语数×10秒，修改意见输入为3分钟
3. **文件路径**：Windows路径使用正斜杠或双反斜杠
4. **内存使用**：长文档翻译可能占用较多内存，建议分批处理

## 🐛 故障排除

### Elasticsearch连接失败

```bash
# 检查ES是否运行
curl http://localhost:9200

# 检查ES配置
# 编辑 try/rag/es_retriever.py 中的ES地址
```

### 翻译质量不佳

1. 检查术语表是否正确
2. 检查RAG检索是否正常工作
3. 尝试调整LLM参数（temperature等）
4. 使用人工审查功能进行修正

### 超时问题

- 术语审查：每次回到界面时时间会刷新
- 修改意见：有3分钟时间输入
- 可以修改超时时间（在代码中调整）

## 📄 许可证

[根据原项目许可证]

## 🙏 致谢

基于 T-Ragx 项目开发，使用 LangGraph 构建多Agent工作流。
