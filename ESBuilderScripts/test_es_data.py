# test_es_data.py
from elasticsearch import Elasticsearch

# 连接ES
es = Elasticsearch("http://localhost:9200")
INDEX_NAME = "zh_en_translation_memory"

# 1. 统计总文档数（验证导入数量）
count = es.count(index=INDEX_NAME)
print(f"✅ ES索引总文档数：{count['count']}（应和导入的1120条一致）")

# 2. 查看前3条数据（验证字段是否正确）
print("\n📝 前3条数据示例：")
response = es.search(
    index=INDEX_NAME,
    size=3,
    body={"query": {"match_all": {}}}
)
for i, hit in enumerate(response["hits"]["hits"]):
    en_text = hit["_source"].get("en", "无")
    zh_text = hit["_source"].get("zh", "无")
    print(f"第{i+1}条：英文={en_text[:50]} | 中文={zh_text[:50]}")

# 3. 测试中英文检索（验证分词/匹配是否正常）
print("\n🔍 测试英文检索（关键词：Active Learning）：")
en_search = es.search(
    index=INDEX_NAME,
    body={"query": {"match": {"en": "Active Learning"}}}
)
for hit in en_search["hits"]["hits"][:2]:
    print(f"匹配结果：{hit['_source']['en']} → {hit['_source']['zh']}")

print("\n🔍 测试中文检索（关键词：主动学习）：")
zh_search = es.search(
    index=INDEX_NAME,
    body={"query": {"match": {"zh": "主动学习"}}}
)
for hit in en_search["hits"]["hits"][:2]:
    print(f"匹配结果：{hit['_source']['zh']} → {hit['_source']['en']}")