def find_term_context(term: str, source_text: str, context_window: int = 200) -> str:
    """
    在原文中找到包含术语的句子上下文
    
    Args:
        term: 要查找的术语
        source_text: 原文
        context_window: 上下文窗口大小（字符数）
    
    Returns:
        包含术语的句子或上下文片段
    """
    import re
    
    # 转义特殊字符
    term_escaped = re.escape(term)
    
    # 查找术语在原文中的位置（不区分大小写）
    pattern = re.compile(term_escaped, re.IGNORECASE)
    matches = list(pattern.finditer(source_text))
    
    if not matches:
        return "未找到该术语在原文中的位置"
    
    # 取第一个匹配位置
    match = matches[0]
    start = match.start()
    end = match.end()
    
    # 向前向后扩展，找到句子边界
    # 向前查找句子开始（句号、问号、感叹号、换行符）
    sentence_start = start
    for i in range(start, max(0, start - context_window), -1):
        if source_text[i] in '.!?\n':
            sentence_start = i + 1
            break
    else:
        sentence_start = max(0, start - context_window)
    
    # 向后查找句子结束
    sentence_end = end
    for i in range(end, min(len(source_text), end + context_window)):
        if source_text[i] in '.!?\n':
            sentence_end = i + 1
            break
    else:
        sentence_end = min(len(source_text), end + context_window)
    
    # 提取句子并高亮术语
    sentence = source_text[sentence_start:sentence_end].strip()
    
    # 高亮术语（用**标记）
    highlighted = re.sub(
        pattern, 
        lambda m: f"**{m.group(0)}**", 
        sentence, 
        flags=re.IGNORECASE
    )
    
    return highlighted


def review_glossary(auto_glossary: list[dict], source_text: str = "", skip_reviewed: bool = True) -> list[dict]:
    """
    人工审查术语表
    
    Args:
        auto_glossary: 待审查的术语列表
        skip_reviewed: 是否跳过已审查的术语（默认True）
    
    Returns:
        审查后的术语列表（包含已审查和 newly 审查的）
    """
    from .glossary_storage import filter_reviewed_terms, save_reviewed_glossary
    
    print("\n====== 🛑 进入人工术语审查阶段 ======\n")
    
    # 如果启用跳过已审查的术语，先过滤
    if skip_reviewed:
        reviewed_terms, unreviewed_terms = filter_reviewed_terms(auto_glossary)
        
        if reviewed_terms:
            print(f"📚 发现 {len(reviewed_terms)} 个已审查的术语，将自动使用已审查结果：")
            for term in reviewed_terms:
                print(f"   ✓ {term['src']} -> {term.get('suggested_trans', 'N/A')}")
            print()
        
        if not unreviewed_terms:
            print("✅ 所有术语都已审查过，无需再次审查\n")
            # 即使所有术语都已审查过，也保存RAG数据备份
            try:
                import sys
                import os
                current_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.dirname(current_dir)
                if project_root not in sys.path:
                    sys.path.insert(0, project_root)
                
                from rag.es_retriever import export_rag_data_to_file
                print(f"  💾 正在保存RAG数据备份...")
                backup_path = export_rag_data_to_file()
                if backup_path:
                    print(f"  ✅ RAG备份已保存: {backup_path}")
            except Exception as e:
                print(f"  ⚠️  保存RAG备份失败: {e}")
            return reviewed_terms
        
        print(f"📝 需要审查的新术语: {len(unreviewed_terms)} 个\n")
        terms_to_review = unreviewed_terms
    else:
        terms_to_review = auto_glossary
        reviewed_terms = []

    # 审查新术语
    newly_reviewed = []
    for i, term in enumerate(terms_to_review, 1):
        print(f"\n[{i}/{len(terms_to_review)}] 原词: {term['src']}")
        print(f"    当前译名: {term['suggested_trans']}")
        print(f"    类型: {term.get('type')}")
        print(f"    理由: {term.get('rationale')}")
        
        # 显示术语所在的句子上下文
        if source_text:
            context = find_term_context(term['src'], source_text)
            print(f"\n    📝 所在句子:")
            print(f"    {context}")
        print()

        action = input(
            "操作: [Enter=接受 | e=编辑 | d=删除] > "
        ).strip().lower()

        if action == "":
            # 即使接受，也标记为已人工审查
            term["human_reviewed"] = True
            term["human_modified"] = False  # 未修改，只是确认
            newly_reviewed.append(term)

        elif action == "e":
            new_trans = input("👉 新译名: ").strip()
            new_reason = input("👉 修改理由: ").strip()

            # 保存原始建议（如果有的话）
            if "original_suggested_trans" not in term:
                term["original_suggested_trans"] = term.get("suggested_trans", "")
            
            term["suggested_trans"] = new_trans
            term["rationale"] = new_reason or "人工修订"
            term["human_reviewed"] = True
            term["human_modified"] = True  # 标记为人工修改

            newly_reviewed.append(term)

        elif action == "d":
            print("❌ 已删除该术语\n")
            continue

        else:
            print("⚠️ 无效操作，默认接受\n")
            term["human_reviewed"] = True
            term["human_modified"] = False
            newly_reviewed.append(term)

        print("-" * 40)

    # 保存新审查的术语
    if newly_reviewed:
        save_reviewed_glossary(newly_reviewed)
        # 更新到Elasticsearch
        try:
            import sys
            import os
            # 添加项目根目录到路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            
            from rag.es_retriever import batch_update_terms_to_es, export_rag_data_to_file
            es_result = batch_update_terms_to_es(newly_reviewed)
            print(f"  📊 ES更新统计: {es_result}")
        except Exception as e:
            print(f"  ⚠️  更新到ES失败: {e}")
            print(f"  💡 提示: 请确保Elasticsearch服务正在运行")
    
    # 人工介入后，无论是否有新审查的术语，都保存更新后的RAG数据
    try:
        import sys
        import os
        # 添加项目根目录到路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        from rag.es_retriever import export_rag_data_to_file
        print(f"\n  💾 正在保存RAG数据备份...")
        backup_path = export_rag_data_to_file()
        if backup_path:
            print(f"  ✅ RAG备份已保存: {backup_path}")
    except Exception as e:
        print(f"  ⚠️  保存RAG备份失败: {e}")
    
    # 合并已审查和新审查的术语
    final_reviewed = reviewed_terms + newly_reviewed
    
    print(f"\n✅ 术语审查完成: {len(reviewed_terms)} 个已审查 + {len(newly_reviewed)} 个新审查 = {len(final_reviewed)} 个总计\n")
    return final_reviewed
