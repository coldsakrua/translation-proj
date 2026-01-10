from elasticsearch import Elasticsearch
import hashlib
import json
import os
from datetime import datetime

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


def update_term_to_es(term_dict: dict) -> bool:
    """
    将单个术语添加到或更新到Elasticsearch
    
    Args:
        term_dict: 术语字典，包含 'src' (英文) 和 'suggested_trans' (中文) 等字段
    
    Returns:
        是否成功
    """
    try:
        en_text = term_dict.get('src', '').strip()
        zh_text = term_dict.get('suggested_trans', '').strip()
        
        if not en_text or not zh_text:
            print(f"⚠️  术语数据不完整，跳过: {term_dict}")
            return False
        
        # 生成文档ID（基于英文文本的SHA1哈希）
        doc_id = hashlib.sha1(en_text.encode('utf-8')).hexdigest()
        
        # 构建文档内容
        doc = {
            "en": en_text,
            "zh": zh_text
        }
        
        # 添加额外的元数据（如果存在）
        if 'type' in term_dict:
            doc['term_type'] = term_dict['type']
        if 'rationale' in term_dict:
            doc['rationale'] = term_dict['rationale']
        if 'human_reviewed' in term_dict:
            doc['human_reviewed'] = term_dict['human_reviewed']
        if 'human_modified' in term_dict:
            doc['human_modified'] = term_dict['human_modified']
        if 'reviewed_at' in term_dict:
            doc['reviewed_at'] = term_dict['reviewed_at']
        
        # 使用 upsert 操作（存在则更新，不存在则插入）
        # Elasticsearch 7.x+ 使用 body 参数，8.x+ 可以直接传参
        try:
            # 尝试新版本API（直接传参）
            response = es.update(
                index=INDEX_NAME,
                id=doc_id,
                doc=doc,
                doc_as_upsert=True
            )
        except TypeError:
            # 回退到旧版本API（使用body参数）
            response = es.update(
                index=INDEX_NAME,
                id=doc_id,
                body={
                    "doc": doc,
                    "doc_as_upsert": True
                }
            )
        
        return response.get('result') in ['created', 'updated']
        
    except Exception as e:
        print(f"⚠️  更新术语到ES失败: {e}")
        return False


def batch_update_terms_to_es(terms: list[dict]) -> dict:
    """
    批量将术语添加到或更新到Elasticsearch
    
    Args:
        terms: 术语列表，每个术语包含 'src' 和 'suggested_trans' 等字段
    
    Returns:
        统计信息：{"success": 成功数量, "failed": 失败数量, "total": 总数}
    """
    if not terms:
        return {"success": 0, "failed": 0, "total": 0}
    
    success_count = 0
    failed_count = 0
    
    print(f"\n📤 开始批量更新 {len(terms)} 个术语到Elasticsearch...")
    
    for term in terms:
        if update_term_to_es(term):
            success_count += 1
        else:
            failed_count += 1
    
    result = {
        "success": success_count,
        "failed": failed_count,
        "total": len(terms)
    }
    
    print(f"✅ ES更新完成: 成功 {success_count} 个，失败 {failed_count} 个，总计 {len(terms)} 个")
    
    return result


def export_rag_data_to_file(output_dir: str = "output/rag_backups") -> str:
    """
    导出Elasticsearch中的所有RAG数据到JSON文件
    
    Args:
        output_dir: 输出目录路径
    
    Returns:
        保存的文件路径，失败时返回空字符串
    """
    try:
        # 检查ES连接
        if not es.ping():
            print(f"  ⚠️  无法连接到Elasticsearch，跳过RAG数据导出")
            return ""
        
        # 检查索引是否存在
        if not es.indices.exists(index=INDEX_NAME):
            print(f"  ⚠️  索引 {INDEX_NAME} 不存在，跳过RAG数据导出")
            return ""
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成文件名：年月日时分秒格式
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"rag_backup_{timestamp}.json"
        file_path = os.path.join(output_dir, filename)
        
        # 使用scroll API获取所有数据（处理大量数据）
        all_docs = []
        scroll_size = 1000  # 每次获取1000条
        scroll_id = None
        
        try:
            # 初始搜索 - 尝试新版本API（直接传参）
            try:
                response = es.search(
                    index=INDEX_NAME,
                    query={"match_all": {}},
                    size=scroll_size,
                    scroll='2m'
                )
            except (TypeError, AttributeError):
                # 回退到旧版本API（使用body参数）
                response = es.search(
                    index=INDEX_NAME,
                    body={
                        "query": {"match_all": {}},
                        "size": scroll_size
                    },
                    scroll='2m'
                )
            
            # 获取第一批数据
            scroll_id = response.get('_scroll_id')
            hits = response['hits']['hits']
            all_docs.extend([hit['_source'] for hit in hits])
            
            # 继续滚动获取剩余数据
            while len(hits) > 0:
                try:
                    # 尝试新版本API
                    try:
                        response = es.scroll(
                            scroll_id=scroll_id,
                            scroll='2m'
                        )
                    except (TypeError, AttributeError):
                        # 回退到旧版本API
                        response = es.scroll(
                            scroll_id=scroll_id,
                            scroll='2m'
                        )
                    
                    scroll_id = response.get('_scroll_id')
                    hits = response['hits']['hits']
                    all_docs.extend([hit['_source'] for hit in hits])
                except Exception as scroll_error:
                    print(f"  ⚠️  Scroll获取数据时出错: {scroll_error}")
                    break
            
            # 清理scroll上下文
            if scroll_id:
                try:
                    es.clear_scroll(scroll_id=scroll_id)
                except:
                    pass
            
        except Exception as search_error:
            print(f"  ⚠️  搜索ES数据时出错: {search_error}")
            # 如果scroll失败，尝试简单搜索（仅适用于数据量小的情况）
            try:
                response = es.search(
                    index=INDEX_NAME,
                    body={"query": {"match_all": {}}, "size": 10000}
                )
                all_docs = [hit['_source'] for hit in response['hits']['hits']]
            except:
                raise search_error
        
        # 保存到JSON文件
        if all_docs:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(all_docs, f, ensure_ascii=False, indent=2)
            
            print(f"  💾 RAG数据已导出: {file_path} (共 {len(all_docs)} 条记录)")
            return file_path
        else:
            print(f"  ⚠️  未找到任何RAG数据")
            return ""
        
    except Exception as e:
        print(f"  ⚠️  导出RAG数据失败: {e}")
        import traceback
        traceback.print_exc()
        return ""
