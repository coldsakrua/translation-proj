from elasticsearch import Elasticsearch

es = Elasticsearch("http://localhost:9200")
INDEX_NAME = "zh_en_translation_memory"

def retrieve_translation_memory(term: str, top_k: int = 3) -> str:
    """
    用术语检索翻译记忆，返回可直接喂给 LLM 的文本
    """
    # 1. 统计总文档数（验证导入数量）,用于测试ES是否能够正常运行
    # count = es.count(index=INDEX_NAME)
    # print(f"✅ ES索引总文档数：{count['count']}（应和导入的1120条一致）")

    resp = es.search(
        index=INDEX_NAME,
        size=top_k,
        body={
            "query": {
                "multi_match": {
                    "query": term,
                    "fields": ["en^2", "zh"]
                }
            }
        }
    )

    hits = resp["hits"]["hits"]
    if not hits:
        return "No relevant translation memory found."

    snippets = []
    for h in hits:
        src = h["_source"].get("en", "")
        tgt = h["_source"].get("zh", "")
        snippets.append(f"- {src} → {tgt}")

    return "\n".join(snippets)
