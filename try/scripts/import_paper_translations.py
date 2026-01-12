"""
便捷脚本：导入论文翻译对到RAG系统
"""
import sys
import os

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from rag.import_translation_pairs import import_all_paper_translations, import_translation_pairs_to_es

if __name__ == "__main__":
    # 默认导入data目录下所有翻译对
    data_dir = os.path.join(project_root, "data")
    
    print("="*60)
    print("论文翻译对导入工具")
    print("="*60)
    
    result = import_all_paper_translations(data_dir)
    
    if result['success'] > 0:
        print(f"\n√ 成功导入 {result['success']} 个翻译对到RAG系统！")
        print("   现在可以在翻译时使用这些翻译记忆了。")
    else:
        print("\n× 导入失败，请检查Elasticsearch是否运行。")

