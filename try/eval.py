"""
翻译结果评估脚本
用于评估整篇文章的翻译质量，包括：
1. 统计整篇文章的quality_score
2. 多维质量评估指标打分
3. 有监督指标打分（基于参考译文）
"""
import json
import os
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import sys


def convert_numpy_types(obj):
    """
    递归转换numpy类型为Python原生类型，以便JSON序列化
    """
    import numpy as np
    
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_numpy_types(item) for item in obj)
    else:
        return obj

# 添加项目路径
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from utils.translation_evaluator import TranslationEvaluator, load_reference_translations


def load_reference_translations_enhanced(reference_file: str) -> Dict:
    """
    从参考译文文件加载参考译文（增强版，支持按章节和chunk对齐）
    
    Args:
        reference_file: 参考译文JSON文件路径（格式如data/vgg_ch.json）
    
    Returns:
        参考译文字典，格式为 {chapter_id: {chunk_id: translation}}
    """
    if not os.path.exists(reference_file):
        print(f"[WARNING] 参考译文文件不存在: {reference_file}")
        return {}
    
    with open(reference_file, 'r', encoding='utf-8') as f:
        chapters = json.load(f)
    
    reference_dict = {}
    
    for chapter_idx, chapter in enumerate(chapters):
        content = chapter.get('content', '')
        if not content:
            continue
        
        # 按段落分割（假设每个段落对应一个chunk）
        # 先按换行符分割，如果没有换行符则按句号分割
        if '\n' in content:
            paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
        else:
            # 按句号分割，但保留句号
            sentences = content.split('。')
            paragraphs = []
            current_para = ""
            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue
                current_para += sent + "。"
                # 如果段落长度超过200字符，或者遇到明显的段落标记，则分割
                if len(current_para) > 200 or any(marker in sent for marker in ['第', '节', '表', '图']):
                    paragraphs.append(current_para.strip())
                    current_para = ""
            if current_para:
                paragraphs.append(current_para.strip())
        
        # 如果只有一个段落，直接使用整个content
        if not paragraphs:
            paragraphs = [content.strip()]
        
        reference_dict[chapter_idx] = {}
        for chunk_idx, para in enumerate(paragraphs):
            if para:
                reference_dict[chapter_idx][chunk_idx] = para
    
    print(f"√ 加载了 {len(reference_dict)} 个章节的参考译文")
    total_chunks = sum(len(chunks) for chunks in reference_dict.values())
    print(f"  总计 {total_chunks} 个参考译文chunk")
    
    return reference_dict


def collect_all_chunks(output_dir: str) -> List[Tuple[int, int, str]]:
    """
    收集所有chunk文件
    
    Args:
        output_dir: 输出目录（如 try/output/vgg）
    
    Returns:
        List of (chapter_id, chunk_id, chunk_file_path)
    """
    chunks = []
    
    if not os.path.exists(output_dir):
        print(f"[ERROR] 输出目录不存在: {output_dir}")
        return chunks
    
    # 遍历所有章节目录
    for item in os.listdir(output_dir):
        chapter_dir = os.path.join(output_dir, item)
        if not os.path.isdir(chapter_dir) or not item.startswith("chapter_"):
            continue
        
        try:
            chapter_id = int(item.split("_")[1])
        except ValueError:
            continue
        
        # 遍历该章节下的所有chunk文件
        for chunk_file in os.listdir(chapter_dir):
            if not chunk_file.startswith("chunk_") or not chunk_file.endswith(".json"):
                continue
            
            try:
                chunk_id_str = chunk_file.replace("chunk_", "").replace(".json", "")
                chunk_id = int(chunk_id_str)
                chunk_path = os.path.join(chapter_dir, chunk_file)
                chunks.append((chapter_id, chunk_id, chunk_path))
            except ValueError:
                continue
    
    # 按章节ID和chunk ID排序
    chunks.sort(key=lambda x: (x[0], x[1]))
    
    return chunks


def evaluate_translation_results(
    output_dir: str,
    reference_file: Optional[str] = None,
    output_report: Optional[str] = None,
    enabled_metrics: Optional[List[str]] = None
) -> Dict:
    """
    评估翻译结果
    
    Args:
        output_dir: 输出目录（如 try/output/vgg）
        reference_file: 参考译文文件路径（可选）
        output_report: 评估报告输出路径（可选）
        enabled_metrics: 启用的评估指标列表，可选值: ['bleu', 'mqm', 'score']
    
    Returns:
        评估结果字典
    """
    print("="*80)
    print("翻译结果评估")
    print("="*80)
    print(f"输出目录: {output_dir}")
    if reference_file:
        print(f"参考译文: {reference_file}")
    if enabled_metrics:
        print(f"启用的指标: {', '.join(enabled_metrics)}")
    print()
    
    # 1. 收集所有chunk文件
    print("步骤 1: 收集chunk文件...")
    all_chunks = collect_all_chunks(output_dir)
    print(f"  找到 {len(all_chunks)} 个chunk文件")
    
    if not all_chunks:
        return {"error": "未找到任何chunk文件"}
    
    # 2. 加载参考译文
    reference_translations = {}
    if reference_file:
        print("\n步骤 2: 加载参考译文...")
        reference_translations = load_reference_translations_enhanced(reference_file)
    
    # 3. 初始化评估器
    evaluator = TranslationEvaluator(reference_translations, enabled_metrics=enabled_metrics)
    
    # 4. 读取并评估所有chunk
    print("\n步骤 3: 评估chunk...")
    valid_chunks = []
    quality_scores = []
    chunk_results = []
    
    for chapter_id, chunk_id, chunk_path in all_chunks:
        try:
            with open(chunk_path, 'r', encoding='utf-8') as f:
                chunk_data = json.load(f)
            
            source_text = chunk_data.get('source_text', '').strip()
            
            # 跳过source_text为空的chunk
            if not source_text:
                continue
            
            translation = chunk_data.get('translation', '')
            quality_score = chunk_data.get('quality_score', 0)
            glossary = chunk_data.get('glossary', [])
            
            # 获取回译文（从refinement_history中）
            back_translation = None
            refinement_history = chunk_data.get('refinement_history', [])
            if refinement_history:
                last_refinement = refinement_history[-1]
                back_translation = last_refinement.get('back_translation')
            
            valid_chunks.append((chapter_id, chunk_id, chunk_path))
            if quality_score:
                quality_scores.append(quality_score)
            
            # 进行综合评估
            eval_result = evaluator.evaluate_comprehensive(
                source_text=source_text,
                translation=translation,
                back_translation=back_translation,
                glossary=glossary,
                chapter_id=chapter_id,
                chunk_id=chunk_id,
                quality_score=quality_score
            )
            
            chunk_results.append({
                "chapter_id": chapter_id,
                "chunk_id": chunk_id,
                "chunk_file": chunk_path,
                "source_text": source_text[:200] + "..." if len(source_text) > 200 else source_text,
                "translation": translation[:200] + "..." if len(translation) > 200 else translation,
                "quality_score": quality_score,
                "evaluation": eval_result
            })
            
        except Exception as e:
            print(f"  [WARNING] 评估chunk失败 {chunk_path}: {e}")
            continue
    
    print(f"  有效chunk数: {len(valid_chunks)}")
    print(f"  已评估chunk数: {len(chunk_results)}")
    
    if not chunk_results:
        return {"error": "没有有效的chunk可评估"}
    
    # 5. 统计整篇文章的quality_score
    print("\n步骤 4: 统计质量分数...")
    overall_quality_score = 0.0
    if quality_scores:
        overall_quality_score = sum(quality_scores) / len(quality_scores)
    
    print(f"  整篇文章平均quality_score: {overall_quality_score:.2f}/10")
    print(f"  最高分: {max(quality_scores):.2f}/10" if quality_scores else "  N/A")
    print(f"  最低分: {min(quality_scores):.2f}/10" if quality_scores else "  N/A")
    
    # 6. 统计多维评估指标
    print("\n步骤 5: 统计多维评估指标...")
    metric_scores = {}
    unsupervised_scores = []
    supervised_scores = []
    
    for result in chunk_results:
        eval_data = result.get("evaluation", {})
        metrics = eval_data.get("metrics", {})
        
        for metric_name, metric_data in metrics.items():
            if isinstance(metric_data, dict) and "score" in metric_data:
                if metric_name not in metric_scores:
                    metric_scores[metric_name] = []
                metric_scores[metric_name].append(metric_data["score"])
        
        # 收集无监督和有监督分数
        if "unsupervised_avg" in eval_data:
            unsupervised_scores.append(eval_data["unsupervised_avg"])
        if "supervised_avg" in eval_data:
            supervised_scores.append(eval_data["supervised_avg"])
    
    # 定义指标方向（越高越好还是越低越好）
    metric_directions = {
        "back_translation": "higher_is_better",  # 回译一致性，越高越好
        "bleu": "higher_is_better",  # BLEU分数，越高越好
        "edit_distance": "lower_is_better",  # 编辑距离，越低越好（距离越小越好）
        "fluency": "higher_is_better",  # 流畅性，越高越好
        "length_ratio": "closer_to_ideal",  # 长度比，越接近理想值越好
        "number_preservation": "higher_is_better",  # 数字保留度，越高越好
        "quality_score": "higher_is_better",  # 质量分数，越高越好
        "terminology": "higher_is_better",  # 术语一致性，越高越好
        "semantic_similarity": "higher_is_better",  # 语义相似度，越高越好
    }
    
    # 计算各指标的平均值
    metric_summary = {}
    for metric_name, scores in metric_scores.items():
        if scores:
            direction = metric_directions.get(metric_name, "higher_is_better")  # 默认为越高越好
            metric_summary[metric_name] = {
                "average": round(sum(scores) / len(scores), 2),
                "min": round(min(scores), 2),
                "max": round(max(scores), 2),
                "count": len(scores),
                "direction": direction,
                "direction_cn": "越高越好" if direction == "higher_is_better" else ("越低越好" if direction == "lower_is_better" else "越接近理想值越好")
            }
    
    # 计算总体评估分数
    overall_eval_score = 0.0
    if chunk_results:
        eval_scores = [r["evaluation"].get("overall_score", 0) for r in chunk_results if "evaluation" in r]
        if eval_scores:
            overall_eval_score = sum(eval_scores) / len(eval_scores)
    
    print(f"  总体评估分数: {overall_eval_score:.2f}/10")
    if unsupervised_scores:
        print(f"  无监督指标平均: {sum(unsupervised_scores) / len(unsupervised_scores):.2f}/10")
    if supervised_scores:
        print(f"  有监督指标平均: {sum(supervised_scores) / len(supervised_scores):.2f}/10")
    
    # 7. 构建评估报告
    report = {
        "evaluation_info": {
            "output_dir": output_dir,
            "reference_file": reference_file,
            "evaluated_at": datetime.now().isoformat(),
            "total_chunks": len(all_chunks),
            "valid_chunks": len(valid_chunks),
            "evaluated_chunks": len(chunk_results)
        },
        "overall_statistics": {
            "quality_score": {
                "average": round(overall_quality_score, 2),
                "min": round(min(quality_scores), 2) if quality_scores else None,
                "max": round(max(quality_scores), 2) if quality_scores else None,
                "count": len(quality_scores)
            },
            "evaluation_score": {
                "average": round(overall_eval_score, 2),
                "min": round(min([r["evaluation"].get("overall_score", 0) for r in chunk_results if "evaluation" in r]), 2) if chunk_results else None,
                "max": round(max([r["evaluation"].get("overall_score", 0) for r in chunk_results if "evaluation" in r]), 2) if chunk_results else None
            },
            "unsupervised_metrics": {
                "average": round(sum(unsupervised_scores) / len(unsupervised_scores), 2) if unsupervised_scores else None,
                "count": len(unsupervised_scores)
            },
            "supervised_metrics": {
                "average": round(sum(supervised_scores) / len(supervised_scores), 2) if supervised_scores else None,
                "count": len(supervised_scores)
            }
        },
        "metric_summary": metric_summary,
        "chapter_statistics": {},
        "chunk_details": chunk_results
    }
    
    # 按章节统计
    chapter_stats = {}
    for result in chunk_results:
        chapter_id = result["chapter_id"]
        if chapter_id not in chapter_stats:
            chapter_stats[chapter_id] = {
                "chunk_count": 0,
                "quality_scores": [],
                "eval_scores": []
            }
        
        chapter_stats[chapter_id]["chunk_count"] += 1
        if result["quality_score"]:
            chapter_stats[chapter_id]["quality_scores"].append(result["quality_score"])
        if "evaluation" in result:
            eval_score = result["evaluation"].get("overall_score", 0)
            if eval_score:
                chapter_stats[chapter_id]["eval_scores"].append(eval_score)
    
    for chapter_id, stats in chapter_stats.items():
        report["chapter_statistics"][chapter_id] = {
            "chunk_count": stats["chunk_count"],
            "quality_score_avg": round(sum(stats["quality_scores"]) / len(stats["quality_scores"]), 2) if stats["quality_scores"] else None,
            "evaluation_score_avg": round(sum(stats["eval_scores"]) / len(stats["eval_scores"]), 2) if stats["eval_scores"] else None
        }
    
    # 8. 保存评估报告
    if output_report:
        print(f"\n步骤 6: 保存评估报告...")
        os.makedirs(os.path.dirname(output_report) if os.path.dirname(output_report) else ".", exist_ok=True)
        # 转换numpy类型为Python原生类型
        report_serializable = convert_numpy_types(report)
        with open(output_report, 'w', encoding='utf-8') as f:
            json.dump(report_serializable, f, ensure_ascii=False, indent=2)
        print(f"  √ 评估报告已保存: {output_report}")
        
        # 保存指标摘要（单独文件，方便查看）
        metrics_summary_file = output_report.replace('.json', '_metrics_summary.json')
        metrics_summary = {
            "evaluation_info": report["evaluation_info"],
            "metrics_summary": metric_summary,
            "overall_statistics": {
                "quality_score": report["overall_statistics"]["quality_score"],
                "evaluation_score": report["overall_statistics"]["evaluation_score"],
                "unsupervised_metrics": report["overall_statistics"]["unsupervised_metrics"],
                "supervised_metrics": report["overall_statistics"]["supervised_metrics"]
            }
        }
        # 转换numpy类型为Python原生类型
        metrics_summary_serializable = convert_numpy_types(metrics_summary)
        with open(metrics_summary_file, 'w', encoding='utf-8') as f:
            json.dump(metrics_summary_serializable, f, ensure_ascii=False, indent=2)
        print(f"  √ 指标摘要已保存: {metrics_summary_file}")
    else:
        # 默认保存到输出目录
        default_report = os.path.join(output_dir, "evaluation_report.json")
        print(f"\n步骤 6: 保存评估报告...")
        # 转换numpy类型为Python原生类型
        report_serializable = convert_numpy_types(report)
        with open(default_report, 'w', encoding='utf-8') as f:
            json.dump(report_serializable, f, ensure_ascii=False, indent=2)
        print(f"  √ 评估报告已保存: {default_report}")
        
        # 保存指标摘要（单独文件，方便查看）
        metrics_summary_file = os.path.join(output_dir, "metrics_summary.json")
        metrics_summary = {
            "evaluation_info": report["evaluation_info"],
            "metrics_summary": metric_summary,
            "overall_statistics": {
                "quality_score": report["overall_statistics"]["quality_score"],
                "evaluation_score": report["overall_statistics"]["evaluation_score"],
                "unsupervised_metrics": report["overall_statistics"]["unsupervised_metrics"],
                "supervised_metrics": report["overall_statistics"]["supervised_metrics"]
            }
        }
        # 转换numpy类型为Python原生类型
        metrics_summary_serializable = convert_numpy_types(metrics_summary)
        with open(metrics_summary_file, 'w', encoding='utf-8') as f:
            json.dump(metrics_summary_serializable, f, ensure_ascii=False, indent=2)
        print(f"  √ 指标摘要已保存: {metrics_summary_file}")
    
    # 9. 打印摘要
    print("\n" + "="*80)
    print("评估摘要")
    print("="*80)
    print(f"有效chunk数: {len(valid_chunks)}")
    print(f"整篇文章平均quality_score: {overall_quality_score:.2f}/10")
    print(f"总体评估分数: {overall_eval_score:.2f}/10")
    
    if metric_summary:
        print("\n各指标平均分:")
        for metric_name, stats in sorted(metric_summary.items()):
            direction_mark = "↑" if stats.get('direction') == 'higher_is_better' else ("↓" if stats.get('direction') == 'lower_is_better' else "≈")
            direction_text = stats.get('direction_cn', '')
            print(f"  - {metric_name}: {stats['average']}/10 (范围: {stats['min']}-{stats['max']}) {direction_mark} {direction_text}")
    
    if chapter_stats:
        print("\n各章节统计:")
        for chapter_id in sorted(chapter_stats.keys()):
            stats = chapter_stats[chapter_id]
            print(f"  章节 {chapter_id}: {stats['chunk_count']} chunks, "
                  f"quality_score={sum(stats['quality_scores'])/len(stats['quality_scores']):.2f}/10" if stats['quality_scores'] else f"quality_score=N/A")
    
    print("="*80)
    
    return report


def main():
    parser = argparse.ArgumentParser(
        description="评估翻译结果",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本评估（无参考译文）
  python eval.py --output-dir try/output/vgg
  
  # 带参考译文的评估
  python eval.py --output-dir try/output/vgg --gt-dir data/vgg_ch.json
  
  # 指定报告输出路径
  python eval.py --output-dir try/output/vgg --gt-dir data/vgg_ch.json --output-report reports/vgg_evaluation.json
  
  # 只评估BLEU和score指标
  python eval.py --output-dir try/output/vgg --gt-dir data/vgg_ch.json --metrics bleu score
  
  # 只评估MQM指标
  python eval.py --output-dir try/output/vgg --gt-dir data/vgg_ch.json --metrics mqm
        """
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        required=True,
        help="模型输出目录（如 try/output/vgg），包含 chapter_xx/chunk_xxx.json 文件"
    )
    
    parser.add_argument(
        "--gt-dir",
        type=str,
        default=None,
        help="参考译文（Ground Truth）文件路径（如 data/vgg_ch.json）"
    )
    
    parser.add_argument(
        "--output-report",
        type=str,
        default=None,
        help="评估报告输出路径（可选，默认保存到输出目录下的 evaluation_report.json）"
    )
    
    parser.add_argument(
        "--metrics",
        type=str,
        nargs='+',
        choices=['bleu', 'mqm', 'score'],
        default=['bleu', 'mqm', 'score'],
        help="指定要评估的指标，可选: bleu (BLEU分数), mqm (语义相似度/MQM), score (质量分数)。可多选，默认全部启用"
    )
    
    args = parser.parse_args()
    
    # 验证输出目录（尝试多种可能的路径）
    output_dir = args.output_dir
    if not os.path.exists(output_dir):
        # 尝试相对于当前目录的路径
        if output_dir.startswith('try/'):
            # 如果用户输入了 try/xxx，尝试去掉 try/ 前缀
            alt_path = output_dir.replace('try/', '', 1)
            if os.path.exists(alt_path):
                output_dir = alt_path
        elif not os.path.isabs(output_dir):
            # 尝试相对于项目根目录
            project_root = Path(__file__).parent.parent
            abs_path = project_root / output_dir
            if abs_path.exists():
                output_dir = str(abs_path)
                print(f"[INFO] 使用绝对路径: {output_dir}")
    
    if not os.path.exists(output_dir):
        print(f"[ERROR] 输出目录不存在: {args.output_dir}")
        print(f"  当前工作目录: {os.getcwd()}")
        print(f"  尝试的路径: {output_dir}")
        print(f"\n提示: 如果在 try 目录下运行，请使用 'output/vgg' 而不是 'try/output/vgg'")
        return 1
    
    args.output_dir = output_dir
    
    # 验证参考译文文件（如果提供）
    if args.gt_dir:
        gt_file = args.gt_dir
        if not os.path.exists(gt_file):
            # 尝试相对于项目根目录
            project_root = Path(__file__).parent.parent
            alt_path = project_root / gt_file
            if alt_path.exists():
                gt_file = str(alt_path)
                print(f"[INFO] 使用参考译文路径: {gt_file}")
        
        if not os.path.exists(gt_file):
            print(f"[WARNING] 参考译文文件不存在: {args.gt_dir}")
            print("  将进行无监督评估")
            args.gt_dir = None
        else:
            args.gt_dir = gt_file
    
    # 执行评估
    try:
        print(f"启用的评估指标: {', '.join(args.metrics)}")
        report = evaluate_translation_results(
            output_dir=args.output_dir,
            reference_file=args.gt_dir,
            output_report=args.output_report,
            enabled_metrics=args.metrics
        )
        
        if "error" in report:
            print(f"\n[ERROR] 评估失败: {report['error']}")
            return 1
        
        print("\n√ 评估完成")
        return 0
        
    except Exception as e:
        print(f"\n[ERROR] 评估过程出错: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())


# python eval.py --output-dir try/output/vgg --gt-dir data/vgg_ch.json --output-report reports/vgg_evaluation.json
