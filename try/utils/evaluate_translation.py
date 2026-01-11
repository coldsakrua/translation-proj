"""
翻译质量评估脚本
用于批量评估翻译结果
"""
import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional

# 添加项目路径
current_dir = Path(__file__).parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utils.translation_evaluator import TranslationEvaluator, load_reference_translations


def evaluate_single_chunk(chunk_file: str, reference_translations: Optional[Dict] = None):
    """
    评估单个chunk文件
    
    Args:
        chunk_file: chunk文件路径
        reference_translations: 参考译文字典（可选）
    """
    evaluator = TranslationEvaluator(reference_translations)
    result = evaluator.evaluate_chunk_file(chunk_file, reference_translations)
    
    print("\n" + "="*60)
    print(f"📊 Chunk评估结果: {chunk_file}")
    print("="*60)
    
    if "error" in result:
        print(f"❌ 错误: {result['error']}")
        return
    
    print(f"\n总体分数: {result['overall_score']}/10")
    
    if "unsupervised_avg" in result:
        print(f"无监督指标平均分: {result['unsupervised_avg']}/10")
    if "supervised_avg" in result:
        print(f"有监督指标平均分: {result['supervised_avg']}/10")
    
    print("\n详细指标:")
    for metric_name, metric_data in result.get("metrics", {}).items():
        if isinstance(metric_data, dict) and "score" in metric_data:
            print(f"  - {metric_name}: {metric_data['score']}/10")
            if "details" in metric_data:
                print(f"    {metric_data['details']}")
    
    return result


def evaluate_chapter(
    book_id: str,
    chapter_id: int,
    num_chunks: int,
    reference_file: Optional[str] = None
):
    """
    评估整个章节
    
    Args:
        book_id: 书籍ID
        chapter_id: 章节ID
        num_chunks: chunk数量
        reference_file: 参考译文文件路径（可选）
    """
    # 加载参考译文
    reference_translations = None
    if reference_file and os.path.exists(reference_file):
        print(f"📖 加载参考译文: {reference_file}")
        reference_translations = load_reference_translations(reference_file)
        print(f"  加载了 {len(reference_translations)} 个章节的参考译文")
    
    evaluator = TranslationEvaluator(reference_translations)
    result = evaluator.evaluate_chapter(book_id, chapter_id, num_chunks, reference_translations)
    
    print("\n" + "="*60)
    print(f"📊 章节 {chapter_id} 评估结果")
    print("="*60)
    
    if "error" in result:
        print(f"❌ 错误: {result['error']}")
        return
    
    print(f"\n章节平均分: {result['average_score']}/10")
    print(f"评估chunk数: {result['num_chunks']}")
    
    print("\n各指标统计:")
    for metric_name, stats in result.get("metric_summary", {}).items():
        print(f"  - {metric_name}:")
        print(f"    平均: {stats['average']}/10")
        print(f"    范围: {stats['min']}/10 - {stats['max']}/10")
    
    print("\n各chunk分数:")
    for i, score in enumerate(result.get("chunk_scores", [])):
        print(f"  Chunk {i}: {score}/10")
    
    # 保存评估结果
    output_file = f"output/{book_id}/chapter_{chapter_id}/evaluation_result.json"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 评估结果已保存: {output_file}")
    
    return result


def evaluate_book(
    book_id: str,
    max_chapters: Optional[int] = None,
    reference_file: Optional[str] = None
):
    """
    评估整本书
    
    Args:
        book_id: 书籍ID
        max_chapters: 最大章节数（可选）
        reference_file: 参考译文文件路径（可选）
    """
    # 加载参考译文
    reference_translations = None
    if reference_file and os.path.exists(reference_file):
        print(f"📖 加载参考译文: {reference_file}")
        reference_translations = load_reference_translations(reference_file)
    
    evaluator = TranslationEvaluator(reference_translations)
    
    book_results = []
    chapter_scores = []
    
    # 查找所有章节
    book_dir = f"output/{book_id}"
    if not os.path.exists(book_dir):
        print(f"❌ 书籍目录不存在: {book_dir}")
        return
    
    chapters = []
    for item in os.listdir(book_dir):
        if item.startswith("chapter_") and os.path.isdir(os.path.join(book_dir, item)):
            try:
                chapter_id = int(item.split("_")[1])
                chapters.append(chapter_id)
            except:
                pass
    
    chapters.sort()
    
    if max_chapters:
        chapters = chapters[:max_chapters]
    
    print(f"\n📚 开始评估书籍: {book_id}")
    print(f"   章节数: {len(chapters)}")
    
    for chapter_id in chapters:
        chapter_dir = os.path.join(book_dir, f"chapter_{chapter_id}")
        
        # 统计chunk数量
        chunk_files = [f for f in os.listdir(chapter_dir) if f.startswith("chunk_") and f.endswith(".json")]
        num_chunks = len(chunk_files)
        
        if num_chunks == 0:
            continue
        
        print(f"\n评估章节 {chapter_id}...")
        result = evaluator.evaluate_chapter(book_id, chapter_id, num_chunks, reference_translations)
        
        if "error" not in result:
            book_results.append(result)
            chapter_scores.append(result["average_score"])
    
    if not book_results:
        print("❌ 未找到任何评估结果")
        return
    
    # 书籍总体统计
    print("\n" + "="*60)
    print(f"📚 书籍 {book_id} 总体评估结果")
    print("="*60)
    
    overall_avg = sum(chapter_scores) / len(chapter_scores) if chapter_scores else 0
    print(f"\n书籍平均分: {overall_avg:.2f}/10")
    print(f"评估章节数: {len(book_results)}")
    
    # 各指标总体统计
    all_metrics = {}
    for result in book_results:
        for metric_name, stats in result.get("metric_summary", {}).items():
            if metric_name not in all_metrics:
                all_metrics[metric_name] = []
            all_metrics[metric_name].append(stats["average"])
    
    print("\n各指标总体平均:")
    for metric_name, scores in all_metrics.items():
        avg = sum(scores) / len(scores)
        print(f"  - {metric_name}: {avg:.2f}/10")
    
    # 保存书籍评估结果
    book_output_file = f"output/{book_id}/book_evaluation_result.json"
    with open(book_output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "book_id": book_id,
            "overall_score": round(overall_avg, 2),
            "num_chapters": len(book_results),
            "chapter_results": book_results,
            "metric_summary": {k: round(sum(v)/len(v), 2) for k, v in all_metrics.items()}
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 书籍评估结果已保存: {book_output_file}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="翻译质量评估工具")
    parser.add_argument("--book", type=str, help="书籍ID")
    parser.add_argument("--chapter", type=int, help="章节ID")
    parser.add_argument("--chunk", type=str, help="chunk文件路径")
    parser.add_argument("--reference", type=str, help="参考译文文件路径")
    parser.add_argument("--max-chapters", type=int, help="最大章节数")
    
    args = parser.parse_args()
    
    if args.chunk:
        # 评估单个chunk
        reference_translations = None
        if args.reference:
            reference_translations = load_reference_translations(args.reference)
        evaluate_single_chunk(args.chunk, reference_translations)
    elif args.book and args.chapter is not None:
        # 评估章节
        # 需要先统计chunk数量
        chapter_dir = f"output/{args.book}/chapter_{args.chapter}"
        if os.path.exists(chapter_dir):
            chunk_files = [f for f in os.listdir(chapter_dir) if f.startswith("chunk_") and f.endswith(".json")]
            num_chunks = len(chunk_files)
            evaluate_chapter(args.book, args.chapter, num_chunks, args.reference)
        else:
            print(f"❌ 章节目录不存在: {chapter_dir}")
    elif args.book:
        # 评估整本书
        evaluate_book(args.book, args.max_chapters, args.reference)
    else:
        print("请指定要评估的内容：--chunk, --chapter 或 --book")
        print("\n示例:")
        print("  python evaluate_translation.py --chunk output/YOLO/chapter_1/chunk_000.json")
        print("  python evaluate_translation.py --book YOLO --chapter 1 --reference data/3_ch.json")
        print("  python evaluate_translation.py --book YOLO --reference data/3_ch.json")

