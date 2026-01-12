# 基于多智能体工作流的长文本领域书籍翻译智能代理

基于 LangGraph 多智能体工作流和 RAG（检索增强生成）的智能翻译系统，专为长文本领域书籍（如AI论文）翻译设计。系统采用章节级翻译策略，通过术语一致性管理、TEaR迭代优化和人工审查机制，确保翻译质量达到出版级标准。

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

- **多智能体工作流**：基于 LangGraph 的翻译工作流，包含风格分析、术语识别、RAG检索、翻译生成、质量评估、迭代修正等节点
- **RAG增强翻译（可选）**：使用 Elasticsearch 检索翻译记忆和术语库，提供上下文增强；支持禁用RAG的直接翻译模式
- **TEaR迭代优化**：Translate（翻译）→ Estimate（评估）→ Refine（修正）循环，自动提升翻译质量（最多3次迭代）
- **术语一致性管理**：自动识别术语，支持章节级批量审查，确保全书术语统一
- **章节级翻译策略**：支持长文档分章节翻译，保持上下文连贯性；章节级人工审查，减少中断成本
- **质量评分系统**：自动评估翻译质量（0-10分），支持回译一致性、术语一致性、长度比例、流畅性等多维度评估
- **速率限制保护**：自动模式下内置速率限制器，防止超过API调用限制（默认每分钟20次）

### 人工介入功能

- **术语审查**：批量显示所有术语，支持按ID修改，超时自动接受
- **章节翻译审查**：审查章节翻译质量，支持反馈意见和重新翻译
- **超时机制**：所有人工介入步骤支持超时自动跳过，适合批量处理

### 辅助功能

- **交互式翻译**：对话式翻译工具，支持严谨/通俗两种翻译风格
- **翻译记忆导入**：支持导入已有论文翻译对到RAG系统
- **质量评估工具**：独立的评估脚本，支持批量评估翻译质量并生成报告
- **自动模式**：支持禁用人工审查和/或RAG检索，全自动翻译流程
- **多种运行模式**：
  - `--no-human-review`：禁用人工审查，自动接受所有术语和翻译
  - `--no-rag`：禁用RAG检索，直接翻译（不使用翻译记忆）
  - 组合使用：`--no-human-review --no-rag`：完全自动模式，无RAG增强

## 🏗️ 系统架构

### 工作流节点（LangGraph）

```
START
  ↓
[分析风格] → [提取术语] → [搜索术语（RAG）] → [翻译生成]
                                              ↓
                                    ┌─────────┴─────────┐
                                    ↓                   ↓
                              [RAG禁用]            [RAG启用]
                                    ↓                   ↓
                              [持久化保存]        [质量评估（TEaR）]
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

**关键特性**：
- **条件路由**：根据 `use_rag` 标志决定是否跳过TEaR环节
- **质量门控**：质量评分 >= 7 或达到最大迭代次数（3次）时停止修正
- **速率限制**：在 `enable_human_review=False` 时，所有LLM调用前进行速率限制检查

### 核心组件

- **TranslationState**：LangGraph状态（TypedDict），包含原文、译文、术语表、质量评分、修正历史等
- **RAG检索器**：Elasticsearch检索翻译记忆和术语（可选，可通过 `--no-rag` 禁用）
- **术语管理器**：术语识别、标准化、一致性检查；章节级批量审查
- **质量评估器**：多维度翻译质量评估（回译一致性、术语一致性、长度比例、流畅性等）
- **人工审查模块**：术语和翻译质量的人工审查接口；支持超时自动接受
- **速率限制器**：自动模式下的API调用速率控制（默认每分钟20次）

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

# 启用人工审查和RAG（默认模式）
python main.py --paper-id vgg

# 禁用人工审查（自动模式，启用RAG）
python main.py --paper-id vgg --no-human-review

# 禁用RAG检索（直接翻译模式，启用人工审查）
python main.py --paper-id vgg --no-rag

# 完全自动模式（禁用人工审查和RAG）
python main.py --paper-id vgg --no-human-review --no-rag

# 指定JSON文件路径
python main.py --json-path D:/hw/translation-proj/data/vgg_en.json --paper-id vgg
```

**参数说明**：
- `--paper-id`: 论文ID（默认: vgg）
- `--json-path`: JSON文件路径（可选，默认使用 `data/{paper-id}_en.json`）
- `--no-human-review`: 禁用人工审查，自动接受所有术语和翻译（启用速率限制保护）
- `--no-rag`: 禁用RAG检索，直接翻译（不使用翻译记忆库）

**运行模式对比**：

| 模式 | 人工审查 | RAG检索 | 速率限制 | 适用场景 |
|------|---------|---------|---------|----------|
| 默认 | ✅ | ✅ | ❌ | 高质量翻译，需要人工把关 |
| `--no-human-review` | ❌ | ✅ | ✅ | 批量处理，有RAG增强 |
| `--no-rag` | ✅ | ❌ | ❌ | 不使用历史翻译记忆 |
| `--no-human-review --no-rag` | ❌ | ❌ | ✅ | 完全自动，无RAG增强 |

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
- 系统自动将章节分割为chunks（逻辑块，保留上下文）
- 对每个chunk执行完整翻译流程：
  - 风格分析（识别领域、语体）
  - 术语提取（命名实体、领域术语、文化负载词）
  - RAG检索（如果启用）：从Elasticsearch检索翻译记忆和术语
  - 翻译生成（注入术语表、章节摘要、历史上下文）
  - 质量评估（如果启用RAG）：TEaR循环（最多3次迭代）
- 生成翻译和质量评分，保存到 `chunk_*.json`

**Phase 2: 术语审查（如果启用人工审查）**
- 收集整个章节的术语（去重）
- 批量显示术语列表，支持按ID修改
- 超时时间：术语数 × 10秒
- 每次回到界面时时间刷新
- 审查后的术语会更新到所有chunk文件，并自动更新译文中的术语翻译

**Phase 3: 生成章节摘要**
- 基于翻译结果生成章节摘要
- 用于后续章节的上下文参考（注入到后续chunk的prompt中）

**Phase 4: 章节翻译质量审查（如果启用人工审查）**
- 显示翻译统计和质量评分
- 用户选择接受/不接受/跳过
- 如果不接受，可输入修改意见（3分钟超时）
- 根据反馈自动重新翻译所有chunks（最多3次重试）

#### 4. 输出结果

翻译结果保存在 `try/output/{book_id}/` 目录：

**章节级输出** (`chapter_{id}/`):
- `chunk_{id:03d}.json`: 每个chunk的翻译结果（包含原文、译文、术语表、质量评分、修正历史等）
- `quality_scores.json`: 质量评分汇总（如果启用人工审查）

**书籍级输出**:
- `chapter_summaries.json`: 所有章节的摘要（用于跨章节上下文）
- `translation_memory.json`: 翻译记忆库（用于后续章节的上下文检索）
- `reviewed_glossary.json`: 全局术语表（跨章节术语一致性）

**评估报告** (`try/reports/`):
- `{book_id}_evaluation.json`: 详细的评估结果（每个chunk的评估详情）
- `{book_id}_evaluation_metrics_summary.json`: 评估指标汇总（质量评分、回译一致性、术语一致性等）

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

### TEaR迭代优化流程（仅在启用RAG时执行）

```
翻译生成
   ↓
质量评估（TEaR）
   ├─ 回译一致性（Back-translation）
   ├─ 术语一致性（Terminology）
   ├─ 长度比例（Length Ratio）
   ├─ 流畅性（Fluency）
   ├─ 数字保留（Number Preservation）
   └─ 综合评分（Quality Score: 0-10）
   ↓
评分 >= 7 或 revision_count >= 3?
   ├─ 是 → 保存结果
   └─ 否 → 修正翻译（根据评估反馈针对性修正）
              ↓
        重新评估
              ↓
        循环（最多3次迭代）
```

**注意**：当使用 `--no-rag` 时，系统会跳过TEaR环节，直接保存翻译结果。

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

### 4. 自动模式与速率限制

使用 `--no-human-review` 参数：
- 自动接受所有术语
- 自动接受章节翻译
- 跳过所有人工介入步骤
- **启用速率限制保护**：内置 `RateLimiter`，确保LLM调用不超过每分钟20次
  - 滑动窗口统计最近1分钟的调用次数
  - 最小调用间隔：3秒（60秒/20次）
  - 在每次 `llm.invoke()` 前自动检查并等待
- 适合批量处理和自动化场景

**速率限制工作原理**：
- 当 `enable_human_review=False` 时，所有LLM调用前会调用 `_rate_limiter.wait_if_needed()`
- 如果最近1分钟内调用次数 >= 20，会等待直到最早的调用超过1分钟
- 确保调用间隔至少为 3秒，避免触发API限流

### 5. 翻译风格选择

交互式翻译支持两种风格：
- **严谨风格（rigorous）**：保持专业术语，适合AI论文
- **通俗风格（popular）**：减少专业术语，更易理解

### 6. 质量评估工具

系统提供独立的评估脚本，用于批量评估翻译质量：

```bash
cd try
python eval.py --paper-id vgg
```

**功能**：
- 批量评估所有chunk的翻译质量
- 生成详细的评估报告（`try/reports/{paper_id}_evaluation.json`）
- 生成评估指标汇总（`try/reports/{paper_id}_evaluation_metrics_summary.json`）
- 支持多种评估指标：质量评分、回译一致性、术语一致性、长度比例、流畅性、数字保留、BLEU、语义相似度、编辑距离等

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

1. **Elasticsearch服务**：
   - 如果使用RAG功能，确保ES服务正在运行（默认 `http://localhost:9200`）
   - 如果禁用RAG（`--no-rag`），则不需要ES服务
   - 检查ES是否运行：`curl http://localhost:9200`

2. **超时设置**：
   - 术语审查超时：术语数 × 10秒（每次回到界面时时间刷新）
   - 修改意见输入：3分钟超时
   - 章节翻译审查：3分钟超时

3. **文件路径**：
   - Windows路径使用正斜杠或双反斜杠
   - 默认数据路径：`data/{paper_id}_en.json`
   - 默认输出路径：`try/output/{book_id}/`

4. **内存使用**：
   - 长文档翻译可能占用较多内存，建议分批处理
   - RAG检索会占用一定内存，如果内存不足可考虑禁用RAG

5. **速率限制**：
   - 自动模式（`--no-human-review`）下会自动启用速率限制
   - 如果遇到API限流错误，系统会自动重试（最多3次）
   - 速率限制器确保调用频率不超过每分钟20次

6. **RAG数据备份**：
   - RAG数据会在术语审查后自动备份到 `try/output/rag_backups/`
   - 备份文件名格式：`rag_backup_{timestamp}.json`

## 🐛 故障排除

### Elasticsearch连接失败

```bash
# 检查ES是否运行
curl http://localhost:9200

# 如果ES未运行，启动ES服务
# Windows: 运行 ESBuilderScripts/start_es.bat
# Linux/Mac: bin/elasticsearch

# 检查ES配置
# 编辑 try/rag/es_retriever.py 中的ES地址
```

**解决方案**：
- 如果不需要RAG功能，使用 `--no-rag` 参数跳过ES依赖
- 如果需要RAG但ES未运行，系统会提示错误并退出

### 翻译质量不佳

1. **检查术语表**：确保术语表正确，使用人工审查功能修正术语
2. **检查RAG检索**：如果启用RAG，检查ES是否正常运行，检索是否返回相关结果
3. **调整LLM参数**：编辑 `try/core/get_llm.py`，调整 `temperature` 等参数
4. **使用人工审查**：启用人工审查模式，在关键质量控制点进行人工修正
5. **检查上下文**：确保章节摘要和全局术语表正确生成和注入

### 速率限制错误

如果遇到API速率限制错误（429错误）：
- **自动模式**：系统会自动启用速率限制器，但仍可能遇到突发限流
- **人工审查模式**：速率限制器不启用，如果遇到限流，需要手动等待
- **解决方案**：
  - 检查API配额和限流设置
  - 在自动模式下，系统会自动重试（最多3次）
  - 如果持续遇到限流，考虑降低并发或增加延迟

### 超时问题

- **术语审查**：每次回到界面时时间会刷新（术语数 × 10秒）
- **修改意见**：有3分钟时间输入
- **章节审查**：有3分钟时间选择接受/不接受
- **自定义超时**：可以修改 `try/utils/human.py` 和 `try/main.py` 中的超时设置

### 内存不足

如果遇到内存不足问题：
- 禁用RAG检索（`--no-rag`）可以减少内存占用
- 分批处理章节，不要一次性处理整本书
- 清理不需要的翻译记忆和备份文件

