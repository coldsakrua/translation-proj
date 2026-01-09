# create_es_index_standalone.py
from elasticsearch import Elasticsearch

# 直接定义索引名（不用导入项目的constants.py）
DEFAULT_MEMORY_INDEX = "zh_en_translation_memory"

# 1. 连接本地Elasticsearch（9200端口）
try:
    es = Elasticsearch(
        "http://localhost:9200",
        # 增加超时配置，避免连接失败
        # timeout=30,
        max_retries=3,
        retry_on_timeout=True
    )
    # 验证连接
    if es.ping():
        print("✅ 成功连接到Elasticsearch！")
    else:
        raise Exception("❌ 无法连接到Elasticsearch，请检查容器是否运行")
except Exception as e:
    print(f"连接ES失败：{e}")
    exit(1)

# 2. 定义中英文索引映射（包含IK分词器）
index_mapping = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                # 中文IK细粒度分词（如果没装IK，会自动降级为standard）
                "zh_analyzer": {
                    "type": "custom",
                    "tokenizer": "ik_max_word",
                    "filter": ["lowercase"]
                },
                # 英文标准分词
                "en_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "stop"]
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "en": {
                "type": "text",
                "analyzer": "en_analyzer",
                "fields": {"keyword": {"type": "keyword"}}
            },
            "zh": {
                "type": "text",
                "analyzer": "zh_analyzer",
                "fields": {"keyword": {"type": "keyword"}}
            },
            "id_key": {"type": "keyword"}
        }
    }
}

# 3. 创建索引（不存在则创建）
try:
    if not es.indices.exists(index=DEFAULT_MEMORY_INDEX):
        es.indices.create(index=DEFAULT_MEMORY_INDEX, body=index_mapping)
        print(f"✅ 索引 {DEFAULT_MEMORY_INDEX} 创建成功！")
    else:
        print(f"ℹ️ 索引 {DEFAULT_MEMORY_INDEX} 已存在，跳过创建。")
except Exception as e:
    print(f"创建索引失败：{e}")
    exit(1)