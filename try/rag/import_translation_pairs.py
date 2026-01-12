"""
导入已有论文翻译对到RAG系统
支持从JSON格式的中英文对照文件中导入翻译对
"""
import json
import os
import sys
from typing import List, Dict, Tuple
import re
from datetime import datetime

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from rag.es_retriever import es, INDEX_NAME, update_term_to_es
from elasticsearch.helpers import bulk


def split_into_sentences(text: str) -> List[str]:
    """
    将文本切分成句子
    
    Args:
        text: 待切分的文本
    
    Returns:
        句子列表
    """
    # 使用正则表达式切分句子（支持中英文）
    # 匹配句号、问号、感叹号，以及换行符
    sentences = re.split(r'[.!?。！？]\s+|\n+', text)
    # 过滤空句子和过短的句子
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    return sentences


def load_translation_pairs(en_file: str, zh_file: str) -> List[Dict[str, str]]:
    """
    从JSON文件加载中英文对照的翻译对
    
    Args:
        en_file: 英文JSON文件路径
        zh_file: 中文JSON文件路径
    
    Returns:
        翻译对列表，每个元素包含：en, zh, title, level, chapter_index
    """
    try:
        with open(en_file, 'r', encoding='utf-8') as f:
            en_data = json.load(f)
        with open(zh_file, 'r', encoding='utf-8') as f:
            zh_data = json.load(f)
    except Exception as e:
        print(f"× 读取文件失败: {e}")
        return []
    
    if len(en_data) != len(zh_data):
        print(f"[WARNING] 警告：英文文件有 {len(en_data)} 个章节，中文文件有 {len(zh_data)} 个章节，数量不匹配")
    
    translation_pairs = []
    
    # 按章节匹配
    min_len = min(len(en_data), len(zh_data))
    for i in range(min_len):
        en_chapter = en_data[i]
        zh_chapter = zh_data[i]
        
        en_title = en_chapter.get('title', '')
        zh_title = zh_chapter.get('title', '')
        en_content = en_chapter.get('content', '')
        zh_content = zh_chapter.get('content', '')
        level = en_chapter.get('level', 0)
        
        if not en_content or not zh_content:
            continue
        
        # 将内容切分成句子
        en_sentences = split_into_sentences(en_content)
        zh_sentences = split_into_sentences(zh_content)
        
        # 如果句子数量不匹配，尝试按段落匹配
        if len(en_sentences) != len(zh_sentences):
            # 尝试按段落匹配（以双换行符分割）
            en_paragraphs = [p.strip() for p in en_content.split('\n\n') if p.strip()]
            zh_paragraphs = [p.strip() for p in zh_content.split('\n\n') if p.strip()]
            
            if len(en_paragraphs) == len(zh_paragraphs):
                # 使用段落作为翻译对
                for j, (en_para, zh_para) in enumerate(zip(en_paragraphs, zh_paragraphs)):
                    if len(en_para) > 20 and len(zh_para) > 10:  # 过滤太短的段落
                        translation_pairs.append({
                            'en': en_para,
                            'zh': zh_para,
                            'title': en_title,
                            'zh_title': zh_title,
                            'level': level,
                            'chapter_index': i,
                            'pair_index': j,
                            'source': 'paper_translation',
                            'pair_type': 'paragraph'
                        })
            else:
                # 如果段落也不匹配，使用整个章节内容作为一对
                if len(en_content) > 50 and len(zh_content) > 20:
                    translation_pairs.append({
                        'en': en_content,
                        'zh': zh_content,
                        'title': en_title,
                        'zh_title': zh_title,
                        'level': level,
                        'chapter_index': i,
                        'pair_index': 0,
                        'source': 'paper_translation',
                        'pair_type': 'chapter'
                    })
        else:
            # 句子数量匹配，使用句子作为翻译对
            for j, (en_sent, zh_sent) in enumerate(zip(en_sentences, zh_sentences)):
                if len(en_sent) > 20 and len(zh_sent) > 10:  # 过滤太短的句子
                    translation_pairs.append({
                        'en': en_sent,
                        'zh': zh_sent,
                        'title': en_title,
                        'zh_title': zh_title,
                        'level': level,
                        'chapter_index': i,
                        'pair_index': j,
                        'source': 'paper_translation',
                        'pair_type': 'sentence'
                    })
    
    return translation_pairs


def import_translation_pairs_to_es(
    en_file: str,
    zh_file: str,
    batch_size: int = 100,
    save_json: bool = True,
    json_output_dir: str = "output/imported_translations"
) -> Dict[str, int]:
    """
    将翻译对导入到Elasticsearch
    
    Args:
        en_file: 英文JSON文件路径
        zh_file: 中文JSON文件路径
        batch_size: 批量导入的大小
    
    Returns:
        统计信息：{"success": 成功数量, "failed": 失败数量, "total": 总数}
    """
    print(f"\n开始导入翻译对...")
    print(f"   英文文件: {en_file}")
    print(f"   中文文件: {zh_file}")
    
    # 加载翻译对
    translation_pairs = load_translation_pairs(en_file, zh_file)
    
    if not translation_pairs:
        print("× 未找到任何翻译对")
        return {"success": 0, "failed": 0, "total": 0}
    
    print(f"√ 加载了 {len(translation_pairs)} 个翻译对")
    
    # 检查ES连接
    try:
        if not es.ping():
            print("× 无法连接到Elasticsearch")
            return {"success": 0, "failed": len(translation_pairs), "total": len(translation_pairs)}
    except Exception as e:
        print(f"× Elasticsearch连接失败: {e}")
        return {"success": 0, "failed": len(translation_pairs), "total": len(translation_pairs)}
    
    # 确保索引存在
    if not es.indices.exists(index=INDEX_NAME):
        print(f"创建索引: {INDEX_NAME}")
        try:
            # 尝试使用中文分词器（如果安装了IK插件）
            zh_analyzer = "standard"  # 默认使用standard
            try:
                # 先测试IK分词器是否可用（不同ES版本的API可能不同）
                try:
                    es.indices.analyze(body={"analyzer": "ik_max_word", "text": "测试"})
                except (TypeError, AttributeError):
                    es.indices.analyze(analyzer="ik_max_word", text="测试")
                zh_analyzer = "ik_max_word"
                print(f"  检测到IK中文分词插件，使用ik_max_word分词器")
            except:
                # 如果没有IK插件，使用standard分词器
                print(f"  未检测到IK中文分词插件，使用standard分词器")
            
            es.indices.create(
                index=INDEX_NAME,
                body={
                    "mappings": {
                        "properties": {
                            "en": {"type": "text", "analyzer": "standard"},
                            "zh": {"type": "text", "analyzer": zh_analyzer},
                            "title": {"type": "keyword"},
                            "zh_title": {"type": "keyword"},
                            "level": {"type": "integer"},
                            "chapter_index": {"type": "integer"},
                            "pair_index": {"type": "integer"},
                            "source": {"type": "keyword"},
                            "pair_type": {"type": "keyword"}
                        }
                    }
                }
            )
            print(f"  索引创建成功（中文分词器: {zh_analyzer}）")
        except Exception as e:
            print(f" 创建索引失败（可能已存在）: {e}")
    
    # 批量导入
    success_count = 0
    failed_count = 0
    
    # 使用bulk API批量导入
    actions = []
    for pair in translation_pairs:
        # 生成文档ID（基于英文内容和章节索引）
        import hashlib
        doc_id_str = f"{pair['en']}_{pair['chapter_index']}_{pair['pair_index']}"
        doc_id = hashlib.sha1(doc_id_str.encode('utf-8')).hexdigest()
        
        action = {
            "_index": INDEX_NAME,
            "_id": doc_id,
            "_source": pair
        }
        actions.append(action)
        
        # 达到批量大小时执行导入
        if len(actions) >= batch_size:
            try:
                success, failed = bulk(es, actions, raise_on_error=False)
                success_count += success
                failed_count += len(failed) if failed else 0
                actions = []
                print(f"  已导入 {success_count} 个翻译对...", end='\r')
            except Exception as e:
                print(f"\n  [WARNING] 批量导入出错: {e}")
                failed_count += len(actions)
                actions = []
    
    # 导入剩余的
    if actions:
        try:
            success, failed = bulk(es, actions, raise_on_error=False)
            success_count += success
            failed_count += len(failed) if failed else 0
        except Exception as e:
            print(f"\n  [WARNING] 批量导入出错: {e}")
            failed_count += len(actions)
    
    print(f"\n√ 导入完成: 成功 {success_count} 个，失败 {failed_count} 个，总计 {len(translation_pairs)} 个")
    
    # 保存到JSON文件（如果启用）
    json_path = None
    if save_json and translation_pairs:
        try:
            # 确保使用绝对路径
            if not os.path.isabs(json_output_dir):
                json_output_dir = os.path.join(project_root, json_output_dir)
            os.makedirs(json_output_dir, exist_ok=True)
            # 从文件名提取基础名称
            base_name = os.path.splitext(os.path.basename(en_file))[0].replace('_en', '')
            json_filename = f"{base_name}_imported.json"
            json_path = os.path.join(json_output_dir, json_filename)
            
            # 保存翻译对
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "source_files": {
                        "en": en_file,
                        "zh": zh_file
                    },
                    "import_statistics": {
                        "total": len(translation_pairs),
                        "success": success_count,
                        "failed": failed_count
                    },
                    "translation_pairs": translation_pairs
                }, f, ensure_ascii=False, indent=2)
            
            print(f"√ 已保存翻译对到JSON文件: {json_path}")
        except Exception as e:
            print(f"[WARNING] 保存JSON文件失败: {e}")
    
    return {
        "success": success_count,
        "failed": failed_count,
        "total": len(translation_pairs),
        "json_path": json_path
    }


def import_all_paper_translations(data_dir: str = "data") -> Dict[str, any]:
    """
    导入data目录下所有的论文翻译对
    
    Args:
        data_dir: 数据目录路径
    
    Returns:
        统计信息
    """
    print(f"\n扫描目录: {data_dir}")
    
    # 查找所有_en.json和_ch.json文件
    en_files = []
    zh_files = []
    
    if os.path.exists(data_dir):
        for filename in os.listdir(data_dir):
            if filename.endswith('_en.json'):
                en_files.append(os.path.join(data_dir, filename))
            elif filename.endswith('_ch.json'):
                zh_files.append(os.path.join(data_dir, filename))
    
    # 匹配文件对
    file_pairs = []
    for en_file in en_files:
        base_name = en_file.replace('_en.json', '')
        zh_file = base_name + '_ch.json'
        if os.path.exists(zh_file):
            file_pairs.append((en_file, zh_file))
        else:
            print(f"[WARNING] 未找到对应的中文文件: {zh_file}")
    
    if not file_pairs:
        print("× 未找到任何翻译对文件")
        return {"total_files": 0, "total_pairs": 0, "success": 0, "failed": 0}
    
    print(f"√ 找到 {len(file_pairs)} 对翻译文件")
    
    # 导入所有文件对
    total_success = 0
    total_failed = 0
    total_pairs = 0
    
    for en_file, zh_file in file_pairs:
        print(f"\n{'='*60}")
        result = import_translation_pairs_to_es(en_file, zh_file)
        total_success += result['success']
        total_failed += result['failed']
        total_pairs += result['total']
    
    print(f"\n{'='*60}")
    print(f"总体统计:")
    print(f"   文件对数: {len(file_pairs)}")
    print(f"   翻译对总数: {total_pairs}")
    print(f"   成功导入: {total_success}")
    print(f"   失败: {total_failed}")
    
    # 生成汇总JSON文件
    try:
        summary_dir = os.path.join(project_root, "output/imported_translations")
        os.makedirs(summary_dir, exist_ok=True)
        summary_path = os.path.join(summary_dir, "import_summary.json")
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump({
                "import_time": __import__('datetime').datetime.now().isoformat(),
                "total_files": len(file_pairs),
                "total_pairs": total_pairs,
                "success": total_success,
                "failed": total_failed,
                "file_pairs": [{"en": en, "zh": zh} for en, zh in file_pairs]
            }, f, ensure_ascii=False, indent=2)
        print(f"\n√ 已保存导入汇总到: {summary_path}")
    except Exception as e:
        print(f"[WARNING] 保存汇总文件失败: {e}")
    
    return {
        "total_files": len(file_pairs),
        "total_pairs": total_pairs,
        "success": total_success,
        "failed": total_failed
    }


def view_imported_translations(json_dir: str = "output/imported_translations") -> List[Dict]:
    """
    查看已导入的翻译对（从JSON文件）
    
    Args:
        json_dir: JSON文件目录
    
    Returns:
        所有翻译对的列表
    """
    all_pairs = []
    
    # 确保使用绝对路径
    if not os.path.isabs(json_dir):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        json_dir = os.path.join(project_root, json_dir)
    
    if not os.path.exists(json_dir):
        print(f"目录不存在: {json_dir}")
        return []
    
    # 查找所有导入的JSON文件（排除汇总文件）
    json_files = [f for f in os.listdir(json_dir) 
                  if f.endswith('_imported.json') and f != 'import_summary.json']
    
    if not json_files:
        print(f"未找到已导入的翻译对文件（目录: {json_dir}）")
        return []
    
    print(f"\n找到 {len(json_files)} 个导入文件:")
    for json_file in json_files:
        file_path = os.path.join(json_dir, json_file)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                pairs = data.get('translation_pairs', [])
                all_pairs.extend(pairs)
                print(f"  - {json_file}: {len(pairs)} 个翻译对")
        except Exception as e:
            print(f"  [WARNING] 读取 {json_file} 失败: {e}")
    
    print(f"\n总计: {len(all_pairs)} 个翻译对")
    return all_pairs


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="导入论文翻译对到RAG系统")
    parser.add_argument("--en", type=str, help="英文JSON文件路径")
    parser.add_argument("--zh", type=str, help="中文JSON文件路径")
    parser.add_argument("--data-dir", type=str, default="data", help="数据目录（自动导入所有翻译对）")
    parser.add_argument("--all", action="store_true", help="导入data目录下所有翻译对")
    parser.add_argument("--view", action="store_true", help="查看已导入的翻译对")
    parser.add_argument("--json-dir", type=str, default="output/imported_translations", help="JSON文件目录（用于--view）")
    
    args = parser.parse_args()
    
    if args.all:
        # 导入所有翻译对
        result = import_all_paper_translations(args.data_dir)
        # 如果指定了--view，导入后自动查看
        if args.view:
            print("\n" + "="*60)
            print("查看已导入的翻译对:")
            print("="*60)
            pairs = view_imported_translations(args.json_dir)
            if pairs:
                print(f"\n前5个翻译对示例:")
                for i, pair in enumerate(pairs[:5], 1):
                    print(f"\n[{i}] {pair.get('title', 'N/A')}")
                    print(f"    英文: {pair.get('en', '')[:100]}...")
                    print(f"    中文: {pair.get('zh', '')[:100]}...")
    elif args.en and args.zh:
        # 导入指定的文件对
        result = import_translation_pairs_to_es(args.en, args.zh)
        # 如果指定了--view，导入后自动查看
        if args.view:
            print("\n" + "="*60)
            print("查看已导入的翻译对:")
            print("="*60)
            pairs = view_imported_translations(args.json_dir)
            if pairs:
                print(f"\n前5个翻译对示例:")
                for i, pair in enumerate(pairs[:5], 1):
                    print(f"\n[{i}] {pair.get('title', 'N/A')}")
                    print(f"    英文: {pair.get('en', '')[:100]}...")
                    print(f"    中文: {pair.get('zh', '')[:100]}...")
    elif args.view:
        # 仅查看已导入的翻译对
        pairs = view_imported_translations(args.json_dir)
        if pairs:
            print(f"\n前5个翻译对示例:")
            for i, pair in enumerate(pairs[:5], 1):
                print(f"\n[{i}] {pair.get('title', 'N/A')}")
                print(f"    英文: {pair.get('en', '')[:100]}...")
                print(f"    中文: {pair.get('zh', '')[:100]}...")
    else:
        print("请指定 --en 和 --zh 参数，或使用 --all 导入所有翻译对，或使用 --view 查看已导入的翻译对")
        print("\n示例:")
        print("  python import_translation_pairs.py --en data/1_en.json --zh data/1_ch.json")
        print("  python import_translation_pairs.py --en D:/hw/translation-proj/data/imagenet_en.json --zh D:/hw/translation-proj/data/imagenet_en.json --view  # 导入并查看")
        print("  python import_translation_pairs.py --all")
        print("  python import_translation_pairs.py --view  # 仅查看")

