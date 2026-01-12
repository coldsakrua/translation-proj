"""
多维翻译质量评估系统
基于MQM（Multidimensional Quality Metrics）思路，提供无监督和有监督评估指标
"""
import json
import os
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import difflib

try:
    from sentence_transformers import SentenceTransformer
    HAS_EMBEDDING = True
except (ImportError, RuntimeError, Exception) as e:
    HAS_EMBEDDING = False
    print(f"[WARNING] sentence-transformers不可用（可能是版本不兼容），语义相似度评估将不可用: {type(e).__name__}")


class TranslationEvaluator:
    """
    翻译质量评估器
    提供多维度的质量评估指标
    """
    
    def __init__(self, reference_translations: Optional[Dict] = None, enabled_metrics: Optional[List[str]] = None):
        """
        初始化评估器
        
        Args:
            reference_translations: 参考译文字典，格式为 {chapter_id: {chunk_id: translation}}
            enabled_metrics: 启用的评估指标列表，可选值: ['bleu', 'mqm', 'score']
                            如果为None，则启用所有可用指标
        """
        self.reference_translations = reference_translations or {}
        self.embedding_model = None
        self.enabled_metrics = enabled_metrics or ['bleu', 'mqm', 'score']  # 默认启用所有
        
        # 如果启用了mqm，尝试加载语义相似度模型
        if 'mqm' in self.enabled_metrics and HAS_EMBEDDING:
            try:
                self.embedding_model = SentenceTransformer('./eval_model')
            except Exception as e:
                print(f"[WARNING] 加载语义相似度模型失败: {e}")
    
    # ==================== 无监督指标 ====================
    
    def evaluate_back_translation_consistency(
        self, 
        source_text: str, 
        translation: str, 
        back_translation: str
    ) -> Dict:
        """
        评估回译一致性（无监督）
        
        Args:
            source_text: 原文
            translation: 译文
            back_translation: 回译文
        
        Returns:
            包含一致性分数的字典
        """
        if not back_translation or back_translation == source_text:
            return {
                "score": 0.0,
                "method": "back_translation_consistency",
                "details": "回译文不可用"
            }
        
        # 使用字符级相似度
        similarity = difflib.SequenceMatcher(None, source_text.lower(), back_translation.lower()).ratio()
        
        # 转换为0-10分
        score = similarity * 10
        
        return {
            "score": round(score, 2),
            "method": "back_translation_consistency",
            "details": f"回译相似度: {similarity:.2%}",
            "similarity": similarity
        }
    
    def evaluate_terminology_consistency(
        self,
        translation: str,
        glossary: List[Dict]
    ) -> Dict:
        """
        评估术语一致性（无监督）
        检查译文是否使用了术语表中的规范译法
        
        Args:
            translation: 译文
            glossary: 术语表
        
        Returns:
            包含术语一致性分数的字典
        """
        if not glossary:
            return {
                "score": 10.0,
                "method": "terminology_consistency",
                "details": "无术语表，跳过检查"
            }
        
        violations = []
        correct_uses = 0
        total_terms = 0
        
        for term in glossary:
            src = term.get('src', '').strip()
            suggested_trans = term.get('suggested_trans', '').strip()
            
            if not src or not suggested_trans:
                continue
            
            total_terms += 1
            
            # 检查原文中是否包含该术语
            if src.lower() in translation.lower():
                # 如果译文直接包含英文原文，可能是术语未翻译
                violations.append({
                    "term": src,
                    "expected": suggested_trans,
                    "issue": "术语未翻译，直接使用英文"
                })
            elif suggested_trans in translation:
                # 正确使用了规范译法
                correct_uses += 1
            else:
                # 检查是否有其他可能的翻译（可能是误译）
                # 这里简化处理，只检查是否使用了规范译法
                pass
        
        if total_terms == 0:
            score = 10.0
        else:
            # 计算正确使用率
            correct_rate = correct_uses / total_terms
            score = correct_rate * 10
        
        return {
            "score": round(score, 2),
            "method": "terminology_consistency",
            "details": f"术语使用: {correct_uses}/{total_terms} 正确",
            "correct_uses": correct_uses,
            "total_terms": total_terms,
            "violations": violations[:5]  # 只返回前5个违规
        }
    
    def evaluate_length_ratio(
        self,
        source_text: str,
        translation: str
    ) -> Dict:
        """
        评估长度比（无监督）
        中英文长度比通常在合理范围内
        
        Args:
            source_text: 原文
            translation: 译文
        
        Returns:
            包含长度比分数的字典
        """
        # 计算字符数（中文按字符，英文按单词）
        source_len = len(source_text.split())
        translation_len = len(translation)
        
        # 中英文长度比通常在1.2-1.8之间比较合理
        # 英文单词数 vs 中文字符数
        ratio = translation_len / source_len if source_len > 0 else 0
        
        # 理想比例约为1.5
        ideal_ratio = 1.5
        deviation = abs(ratio - ideal_ratio) / ideal_ratio
        
        # 偏差越小，分数越高
        score = max(0, 10 * (1 - min(deviation, 1.0)))
        
        return {
            "score": round(score, 2),
            "method": "length_ratio",
            "details": f"长度比: {ratio:.2f} (理想: {ideal_ratio})",
            "ratio": ratio,
            "source_length": source_len,
            "translation_length": translation_len
        }
    
    def evaluate_fluency(
        self,
        translation: str
    ) -> Dict:
        """
        评估流畅性（无监督）
        使用简单的启发式规则
        
        Args:
            translation: 译文
        
        Returns:
            包含流畅性分数的字典
        """
        issues = []
        score = 10.0
        
        # 检查重复字符（可能是错误）
        if re.search(r'(.)\1{4,}', translation):
            issues.append("存在异常重复字符")
            score -= 1.0
        
        # 检查标点符号使用
        if translation.count('。') + translation.count('！') + translation.count('？') == 0:
            if len(translation) > 50:  # 长文本应该有标点
                issues.append("缺少句末标点")
                score -= 0.5
        
        # 检查中英文混排（除了术语）
        # 简单检查：连续英文字母过多可能是错误
        english_chunks = re.findall(r'[a-zA-Z]{10,}', translation)
        if len(english_chunks) > 3:  # 允许少量英文术语
            issues.append("可能存在过多未翻译英文")
            score -= 1.0
        
        # 检查基本的中文语法（句子完整性）
        if len(translation) > 20 and not any(p in translation for p in ['，', '。', '、', '：']):
            issues.append("可能缺少必要的标点符号")
            score -= 0.5
        
        score = max(0, score)
        
        return {
            "score": round(score, 2),
            "method": "fluency",
            "details": f"流畅性检查: {'通过' if not issues else '; '.join(issues)}",
            "issues": issues
        }
    
    def evaluate_number_preservation(
        self,
        source_text: str,
        translation: str
    ) -> Dict:
        """
        评估数字保留度（无监督）
        检查数字、公式等是否被正确保留
        
        Args:
            source_text: 原文
            translation: 译文
        
        Returns:
            包含数字保留度分数的字典
        """
        # 提取原文中的数字
        source_numbers = re.findall(r'\d+\.?\d*', source_text)
        translation_numbers = re.findall(r'\d+\.?\d*', translation)
        
        if not source_numbers:
            return {
                "score": 10.0,
                "method": "number_preservation",
                "details": "原文无数字"
            }
        
        # 检查数字是否都被保留
        source_set = set(source_numbers)
        translation_set = set(translation_numbers)
        
        missing = source_set - translation_set
        preserved = source_set & translation_set
        
        if len(source_set) == 0:
            score = 10.0
        else:
            preservation_rate = len(preserved) / len(source_set)
            score = preservation_rate * 10
        
        return {
            "score": round(score, 2),
            "method": "number_preservation",
            "details": f"数字保留: {len(preserved)}/{len(source_set)}",
            "preserved": len(preserved),
            "total": len(source_set),
            "missing": list(missing)[:5]
        }
    
    # ==================== 有监督指标 ====================
    
    def evaluate_bleu_score(
        self,
        translation: str,
        reference: str
    ) -> Dict:
        """
        计算BLEU分数（有监督）
        简化版BLEU，基于n-gram重叠
        
        Args:
            translation: 译文
            reference: 参考译文
        
        Returns:
            包含BLEU分数的字典
        """
        def get_ngrams(text, n):
            """获取n-gram"""
            words = list(text)
            return [tuple(words[i:i+n]) for i in range(len(words)-n+1)]
        
        # 字符级n-gram（适用于中文）
        translation_1grams = set(get_ngrams(translation, 1))
        translation_2grams = set(get_ngrams(translation, 2))
        reference_1grams = set(get_ngrams(reference, 1))
        reference_2grams = set(get_ngrams(reference, 2))
        
        # 计算precision
        precision_1 = len(translation_1grams & reference_1grams) / len(translation_1grams) if translation_1grams else 0
        precision_2 = len(translation_2grams & reference_2grams) / len(translation_2grams) if translation_2grams else 0
        
        # 简化的BLEU（几何平均）
        bleu = (precision_1 * precision_2) ** 0.5
        
        # 转换为0-10分
        score = bleu * 10
        
        return {
            "score": round(score, 2),
            "method": "bleu_score",
            "details": f"BLEU: {bleu:.4f}",
            "bleu": bleu,
            "precision_1gram": precision_1,
            "precision_2gram": precision_2
        }
    
    def evaluate_semantic_similarity(
        self,
        translation: str,
        reference: str
    ) -> Dict:
        """
        评估语义相似度（有监督）
        使用sentence-transformers计算embedding相似度
        
        Args:
            translation: 译文
            reference: 参考译文
        
        Returns:
            包含语义相似度分数的字典
        """
        if not self.embedding_model:
            return {
                "score": 0.0,
                "method": "semantic_similarity",
                "details": "语义相似度模型未加载"
            }
        
        try:
            # 计算embedding
            embeddings = self.embedding_model.encode([translation, reference])
            
            # 计算余弦相似度
            try:
                import numpy as np
                similarity = np.dot(embeddings[0], embeddings[1]) / (np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1]))
                # 确保转换为Python原生float类型
                similarity = float(similarity)
            except ImportError:
                # 如果没有numpy，使用简单的点积计算
                dot_product = sum(a * b for a, b in zip(embeddings[0], embeddings[1]))
                norm_a = sum(a * a for a in embeddings[0]) ** 0.5
                norm_b = sum(b * b for b in embeddings[1]) ** 0.5
                similarity = float(dot_product / (norm_a * norm_b) if norm_a * norm_b > 0 else 0)
            
            # 转换为0-10分
            score = (similarity + 1) / 2 * 10  # 从[-1,1]映射到[0,10]
            
            return {
                "score": round(float(score), 2),
                "method": "semantic_similarity",
                "details": f"语义相似度: {similarity:.4f}",
                "similarity": float(similarity)
            }
        except Exception as e:
            return {
                "score": 0.0,
                "method": "semantic_similarity",
                "details": f"计算失败: {e}"
            }
    
    def evaluate_edit_distance(
        self,
        translation: str,
        reference: str
    ) -> Dict:
        """
        评估编辑距离（有监督）
        
        Args:
            translation: 译文
            reference: 参考译文
        
        Returns:
            包含编辑距离分数的字典
        """
        # 使用字符级编辑距离
        def levenshtein_distance(s1, s2):
            if len(s1) < len(s2):
                return levenshtein_distance(s2, s1)
            if len(s2) == 0:
                return len(s1)
            
            previous_row = range(len(s2) + 1)
            for i, c1 in enumerate(s1):
                current_row = [i + 1]
                for j, c2 in enumerate(s2):
                    insertions = previous_row[j + 1] + 1
                    deletions = current_row[j] + 1
                    substitutions = previous_row[j] + (c1 != c2)
                    current_row.append(min(insertions, deletions, substitutions))
                previous_row = current_row
            
            return previous_row[-1]
        
        distance = levenshtein_distance(translation, reference)
        max_len = max(len(translation), len(reference))
        
        if max_len == 0:
            similarity = 1.0
        else:
            similarity = 1 - (distance / max_len)
        
        # 转换为0-10分
        score = similarity * 10
        
        return {
            "score": round(score, 2),
            "method": "edit_distance",
            "details": f"编辑距离: {distance}/{max_len}, 相似度: {similarity:.2%}",
            "distance": distance,
            "similarity": similarity
        }
    
    # ==================== 综合评估 ====================
    
    def evaluate_comprehensive(
        self,
        source_text: str,
        translation: str,
        back_translation: Optional[str] = None,
        glossary: Optional[List[Dict]] = None,
        reference: Optional[str] = None,
        chapter_id: Optional[int] = None,
        chunk_id: Optional[int] = None,
        quality_score: Optional[float] = None
    ) -> Dict:
        """
        综合评估翻译质量
        
        Args:
            source_text: 原文
            translation: 译文
            back_translation: 回译文（可选）
            glossary: 术语表（可选）
            reference: 参考译文（可选）
            chapter_id: 章节ID（用于查找参考译文）
            chunk_id: chunk ID（用于查找参考译文）
            quality_score: 已有的质量分数（可选，来自chunk文件）
        
        Returns:
            包含所有评估指标的字典
        """
        results = {
            "source_text": source_text[:100] + "..." if len(source_text) > 100 else source_text,
            "translation": translation[:100] + "..." if len(translation) > 100 else translation,
            "metrics": {},
            "overall_score": 0.0
        }
        
        # 如果启用了score指标，添加quality_score
        if 'score' in self.enabled_metrics and quality_score is not None:
            results["metrics"]["quality_score"] = {
                "score": quality_score,
                "method": "quality_score",
                "details": f"质量分数: {quality_score}/10"
            }
        
        # 无监督指标（基础指标，始终计算）
        unsupervised_scores = []
        
        # 1. 回译一致性
        if back_translation:
            bt_result = self.evaluate_back_translation_consistency(source_text, translation, back_translation)
            results["metrics"]["back_translation"] = bt_result
            unsupervised_scores.append(bt_result["score"])
        
        # 2. 术语一致性
        if glossary:
            term_result = self.evaluate_terminology_consistency(translation, glossary)
            results["metrics"]["terminology"] = term_result
            unsupervised_scores.append(term_result["score"])
        
        # 3. 长度比
        length_result = self.evaluate_length_ratio(source_text, translation)
        results["metrics"]["length_ratio"] = length_result
        unsupervised_scores.append(length_result["score"])
        
        # 4. 流畅性
        fluency_result = self.evaluate_fluency(translation)
        results["metrics"]["fluency"] = fluency_result
        unsupervised_scores.append(fluency_result["score"])
        
        # 5. 数字保留度
        number_result = self.evaluate_number_preservation(source_text, translation)
        results["metrics"]["number_preservation"] = number_result
        unsupervised_scores.append(number_result["score"])
        
        # 有监督指标
        supervised_scores = []
        
        # 尝试获取参考译文
        if not reference and chapter_id is not None and chunk_id is not None:
            if chapter_id in self.reference_translations:
                if chunk_id in self.reference_translations[chapter_id]:
                    reference = self.reference_translations[chapter_id][chunk_id]
        
        if reference:
            # 1. BLEU分数（如果启用）
            if 'bleu' in self.enabled_metrics:
                bleu_result = self.evaluate_bleu_score(translation, reference)
                results["metrics"]["bleu"] = bleu_result
                supervised_scores.append(bleu_result["score"])
            
            # 2. 语义相似度/MQM（如果启用）
            if 'mqm' in self.enabled_metrics:
                semantic_result = self.evaluate_semantic_similarity(translation, reference)
                results["metrics"]["semantic_similarity"] = semantic_result
                # 如果模型可用，才加入分数计算
                if semantic_result["score"] > 0:
                    supervised_scores.append(semantic_result["score"])
            
            # 3. 编辑距离（始终计算，作为基础指标）
            edit_result = self.evaluate_edit_distance(translation, reference)
            results["metrics"]["edit_distance"] = edit_result
            supervised_scores.append(edit_result["score"])
        
        # 计算综合分数
        # 无监督指标权重：0.6，有监督指标权重：0.4（如果有）
        if unsupervised_scores:
            unsupervised_avg = sum(unsupervised_scores) / len(unsupervised_scores)
        else:
            unsupervised_avg = 0
        
        if supervised_scores:
            supervised_avg = sum(supervised_scores) / len(supervised_scores)
            # 有监督和无监督指标加权平均
            overall_score = unsupervised_avg * 0.6 + supervised_avg * 0.4
        else:
            # 只有无监督指标
            overall_score = unsupervised_avg
        
        results["overall_score"] = round(overall_score, 2)
        results["unsupervised_avg"] = round(unsupervised_avg, 2)
        if supervised_scores:
            results["supervised_avg"] = round(supervised_avg, 2)
        
        return results
    
    def evaluate_chunk_file(
        self,
        chunk_file_path: str,
        reference_translations: Optional[Dict] = None
    ) -> Dict:
        """
        评估单个chunk文件
        
        Args:
            chunk_file_path: chunk JSON文件路径
            reference_translations: 参考译文字典（可选）
        
        Returns:
            评估结果
        """
        if not os.path.exists(chunk_file_path):
            return {"error": f"文件不存在: {chunk_file_path}"}
        
        with open(chunk_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        source_text = data.get('source_text', '')
        translation = data.get('translation', '')
        back_translation = data.get('back_translation', '')
        glossary = data.get('glossary', [])
        
        # 尝试从文件路径提取chapter_id和chunk_id
        path_parts = Path(chunk_file_path).parts
        chapter_id = None
        chunk_id = None
        for part in path_parts:
            if part.startswith('chapter_'):
                chapter_id = int(part.split('_')[1])
            if part.startswith('chunk_'):
                chunk_id = int(Path(part).stem.split('_')[1])
        
        # 如果有参考译文，更新
        if reference_translations:
            self.reference_translations = reference_translations
        
        return self.evaluate_comprehensive(
            source_text=source_text,
            translation=translation,
            back_translation=back_translation,
            glossary=glossary,
            chapter_id=chapter_id,
            chunk_id=chunk_id
        )
    
    def evaluate_chapter(
        self,
        book_id: str,
        chapter_id: int,
        num_chunks: int,
        reference_translations: Optional[Dict] = None
    ) -> Dict:
        """
        评估整个章节
        
        Args:
            book_id: 书籍ID
            chapter_id: 章节ID
            num_chunks: chunk数量
            reference_translations: 参考译文字典（可选）
        
        Returns:
            章节评估结果
        """
        if reference_translations:
            self.reference_translations = reference_translations
        
        chunk_results = []
        chapter_scores = []
        
        for chunk_id in range(num_chunks):
            chunk_file = f"output/{book_id}/chapter_{chapter_id}/chunk_{chunk_id:03d}.json"
            if os.path.exists(chunk_file):
                result = self.evaluate_chunk_file(chunk_file, reference_translations)
                if "error" not in result:
                    chunk_results.append(result)
                    chapter_scores.append(result.get("overall_score", 0))
        
        if not chunk_results:
            return {"error": "未找到任何chunk文件"}
        
        # 计算章节平均分
        avg_score = sum(chapter_scores) / len(chapter_scores) if chapter_scores else 0
        
        # 计算各指标的平均分
        metric_averages = {}
        for result in chunk_results:
            for metric_name, metric_data in result.get("metrics", {}).items():
                if metric_name not in metric_averages:
                    metric_averages[metric_name] = []
                if isinstance(metric_data, dict) and "score" in metric_data:
                    metric_averages[metric_name].append(metric_data["score"])
        
        metric_summary = {}
        for metric_name, scores in metric_averages.items():
            metric_summary[metric_name] = {
                "average": round(sum(scores) / len(scores), 2),
                "min": round(min(scores), 2),
                "max": round(max(scores), 2)
            }
        
        return {
            "chapter_id": chapter_id,
            "num_chunks": len(chunk_results),
            "average_score": round(avg_score, 2),
            "chunk_scores": chapter_scores,
            "metric_summary": metric_summary,
            "chunk_details": chunk_results
        }


def load_reference_translations(reference_file: str) -> Dict:
    """
    从参考译文文件加载参考译文
    
    Args:
        reference_file: 参考译文JSON文件路径（格式如data/3_ch.json）
    
    Returns:
        参考译文字典，格式为 {chapter_id: {chunk_id: translation}}
    """
    if not os.path.exists(reference_file):
        return {}
    
    with open(reference_file, 'r', encoding='utf-8') as f:
        chapters = json.load(f)
    
    reference_dict = {}
    
    for chapter_idx, chapter in enumerate(chapters):
        content = chapter.get('content', '')
        if not content:
            continue
        
        # 简单分割（实际应该与翻译时的分割方式一致）
        # 这里假设按段落分割
        paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
        
        reference_dict[chapter_idx] = {}
        for chunk_idx, para in enumerate(paragraphs):
            reference_dict[chapter_idx][chunk_idx] = para
    
    return reference_dict


if __name__ == "__main__":
    # 示例使用
    evaluator = TranslationEvaluator()
    
    # 评估单个chunk
    result = evaluator.evaluate_chunk_file("output/YOLO/chapter_1/chunk_000.json")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    # 评估整个章节
    chapter_result = evaluator.evaluate_chapter("YOLO", 1, 5)
    print("\n章节评估结果:")
    print(json.dumps(chapter_result, ensure_ascii=False, indent=2))

