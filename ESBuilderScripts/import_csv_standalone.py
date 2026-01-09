# import_csv_standalone.py
import pandas as pd
import numpy as np
from elasticsearch import Elasticsearch
from tqdm import tqdm
import hashlib
import json

# 配置（关键：适配你的CSV列名）
CSV_FILE_PATH = "./translation_pairs.csv"  # 你的CSV路径
ES_HOST = "http://localhost:9200"
INDEX_NAME = "zh_en_translation_memory"
BATCH_SIZE = 10000
# 映射：你的CSV列名 → 脚本需要的列名
SOURCE_COL = "source_text"  # 源文本（英文）
TARGET_COL = "target_text"  # 目标文本（中文）
ID_KEY = SOURCE_COL  # 以源文本列为基准生成ID

# 1. 连接ES
es = Elasticsearch(ES_HOST, 
        # timeout=30,
        )
if not es.ping():
    raise Exception("无法连接到Elasticsearch，请检查容器是否运行")

# 2. 文本清洗函数（极简版，和项目逻辑对齐）
def clean_text(text):
    if pd.isna(text):
        return ""
    import re
    text = re.sub(r'\s+', ' ', text).strip()  # 多个空格转一个
    text = re.sub(r'[^\w\s\u4e00-\u9fff]', '', text)  # 保留中英文、数字、空格
    return text

def is_noise(text):
    if pd.isna(text) or len(text) < 3:
        return True
    import re
    if re.match(r'^\d+$', text):  # 纯数字判定为噪音
        return True
    return False

# 3. 读取并过滤CSV
try:
    # 读取CSV（编码不对的话改成encoding="gbk"）
    df = pd.read_csv(CSV_FILE_PATH, encoding="utf-8")
    print(f"✅ 成功读取CSV，共 {len(df)} 行数据")
except Exception as e:
    print(f"读取CSV失败：{e}")
    exit(1)

# 验证核心列是否存在
required_cols = {SOURCE_COL, TARGET_COL}
if not required_cols.intersection(df.columns):
    raise ValueError(
        f"CSV必须包含 '{SOURCE_COL}' 和 '{TARGET_COL}' 列，当前列：{df.columns}\n"
        "如果列名对应错误，请修改脚本里的 SOURCE_COL/TARGET_COL 配置！"
    )

# 重命名列（适配后续逻辑，把source_text→en，target_text→zh）
df.rename(columns={SOURCE_COL: "en", TARGET_COL: "zh"}, inplace=True)
ID_KEY = "en"  # 重命名后ID基准列改为en

# 过滤无效数据
df = df.dropna(subset=["en", "zh"], how="all")  # 移除中英文都为空的行
df = df.drop_duplicates(subset=[ID_KEY])  # 基于英文列去重
df[ID_KEY] = df[ID_KEY].apply(clean_text)  # 清洗英文文本
df = df[~df[ID_KEY].map(is_noise)]  # 移除噪音文本
df["id_key"] = ID_KEY  # 记录ID基准列

# 过滤后数据检查
if len(df) == 0:
    print("⚠️ 过滤后无有效数据，请检查CSV内容！")
    exit(0)
print(f"✅ 过滤后剩余 {len(df)} 条有效数据")

# 4. 批量导入ES
def upsert_doc(record):
    """生成ES的upsert指令（存在则更新，不存在则插入）"""
    # 基于英文列生成唯一ID
    doc_id = hashlib.sha1(record[ID_KEY].encode('utf8')).hexdigest()
    # 移除空值字段
    record = {k: v for k, v in record.items() if not pd.isna(v)}
    # 生成指令
    yield json.dumps({"update": {"_index": INDEX_NAME, "_id": doc_id, "retry_on_conflict": 3}})
    yield json.dumps({"doc": record, "doc_as_upsert": True})

# 分批导入（避免一次性导入过多数据）
batch_idx = np.array_split(range(len(df)), max(int(len(df)/BATCH_SIZE), 1))
for idx in tqdm(batch_idx, desc="导入CSV数据到ES"):
    batch_df = df.iloc[idx]
    bulk_data = []
    for _, row in batch_df.iterrows():
        bulk_data.extend(list(upsert_doc(row.to_dict())))
    # 执行批量导入
    try:
        response = es.bulk(body=bulk_data, index=INDEX_NAME)
        if response.get("errors"):
            print(f"⚠️ 该批次存在导入错误：{response['errors']}")
    except Exception as e:
        print(f"❌ 该批次导入失败：{e}")
        continue

print(f"\n🎉 数据导入完成！共导入 {len(df)} 条中英文翻译数据到ES索引 {INDEX_NAME}")