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
        sentence
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
    
    print("\n====== 进入人工术语审查阶段 ======\n")
    
    # 如果启用跳过已审查的术语，先过滤
    if skip_reviewed:
        reviewed_terms, unreviewed_terms = filter_reviewed_terms(auto_glossary)
        
        if reviewed_terms:
            print(f"发现 {len(reviewed_terms)} 个已审查的术语，将自动使用已审查结果：")
            for term in reviewed_terms:
                print(f"   ✓ {term['src']} -> {term.get('suggested_trans', 'N/A')}")
            print()
        
        if not unreviewed_terms:
            print("√ 所有术语都已审查过，无需再次审查\n")
            # 即使所有术语都已审查过，也保存RAG数据备份
            try:
                import sys
                import os
                current_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.dirname(current_dir)
                if project_root not in sys.path:
                    sys.path.insert(0, project_root)
                
                from rag.es_retriever import export_rag_data_to_file
                print(f"  正在保存RAG数据备份...")
                backup_path = export_rag_data_to_file()
                if backup_path:
                    print(f"  √ RAG备份已保存: {backup_path}")
            except Exception as e:
                print(f"  [WARNING] 保存RAG备份失败: {e}")
            return reviewed_terms
        
        print(f"需要审查的新术语: {len(unreviewed_terms)} 个\n")
        terms_to_review = unreviewed_terms
    else:
        terms_to_review = auto_glossary
        reviewed_terms = []

    # 导入超时输入函数
    from .input_with_timeout import input_with_timeout
    import time
    
    # 初始化所有术语为已审查（默认接受）
    for term in terms_to_review:
        term["human_reviewed"] = True
        term["human_modified"] = False
    
    # 计算总超时时间（术语数 * 10秒）
    total_timeout = len(terms_to_review) * 10
    loop_start_time = time.time()  # 当前循环的开始时间（每次回到界面时刷新）
    
    # 交互式审查循环
    while True:
        # 每次回到主界面时，重置当前循环的计时器（刷新时间）
        loop_start_time = time.time()
        
        # 清屏并显示所有术语
        import os
        os.system('cls' if os.name == 'nt' else 'clear')  # Windows用cls，Linux/Mac用clear
        
        print("\n" + "="*80)
        print("术语审查界面（总超时时间: {}秒）".format(total_timeout))
        print("="*80)
        print(f"剩余时间: {total_timeout} 秒（每次回到界面时刷新）\n")
        
        # 显示所有术语列表
        print(f"{'ID':<5} {'原词':<30} {'当前译名':<30} {'状态':<10}")
        print("-" * 80)
        for i, term in enumerate(terms_to_review, 1):
            status = "已修改" if term.get("human_modified", False) else "已接受"
            print(f"{i:<5} {term['src']:<30} {term.get('suggested_trans', 'N/A'):<30} {status:<10}")
        
        print("\n" + "="*80)
        print("操作说明:")
        print("  - 输入术语ID（1-{}）进行修改".format(len(terms_to_review)))
        print("  - 输入 'd' + ID（如 'd1'）删除该术语")
        print("  - 输入 'q' 或直接回车完成审查（接受所有未修改的术语）")
        print("="*80)
        
        # 计算剩余时间（基于当前循环的开始时间，每次回到界面时刷新）
        elapsed_time = time.time() - loop_start_time
        remaining_time = total_timeout - elapsed_time
        
        if remaining_time <= 0:
            print(f"\n超时（{total_timeout}秒），自动完成审查...")
            break
        
        # 获取用户输入（使用当前循环的剩余时间）
        try:
            user_input = input_with_timeout(
                f"\n请输入操作（剩余 {int(remaining_time)} 秒）> ",
                timeout=remaining_time,
                default="q"
            ).strip().lower()
        except:
            user_input = "q"
        
        if not user_input or user_input == "q":
            # 完成审查
            break
        
        # 处理删除操作
        if user_input.startswith('d'):
            try:
                term_id = int(user_input[1:])
                if 1 <= term_id <= len(terms_to_review):
                    term = terms_to_review[term_id - 1]
                    print(f"\n× 已删除术语: {term['src']}")
                    terms_to_review.remove(term)
                    time.sleep(1)  # 短暂暂停让用户看到删除信息
                    continue
            except ValueError:
                print("[WARNING] 无效的ID格式，请使用 'd1', 'd2' 等")
                time.sleep(1)
                continue
        
        # 处理编辑操作
        try:
            term_id = int(user_input)
            if 1 <= term_id <= len(terms_to_review):
                term = terms_to_review[term_id - 1]
                
                # 显示术语详情
                print("\n" + "-"*80)
                print(f"术语详情 [ID: {term_id}]")
                print("-"*80)
                print(f"原词: {term['src']}")
                print(f"当前译名: {term.get('suggested_trans', 'N/A')}")
                print(f"类型: {term.get('type', 'N/A')}")
                print(f"理由: {term.get('rationale', 'N/A')}")
                
                # 显示上下文
                if source_text:
                    context = find_term_context(term['src'], source_text)
                    print(f"\n所在句子:")
                    print(f"  {context}")
                
                print("-"*80)
                
                # 获取新译名（使用当前循环的剩余时间）
                current_remaining = total_timeout - (time.time() - loop_start_time)
                if current_remaining <= 0:
                    print("时间已到，自动完成审查...")
                    break
                
                new_trans = input_with_timeout(
                    f"新译名（直接回车保持原样，剩余 {int(current_remaining)} 秒）: ",
                    timeout=current_remaining,
                    default=term.get('suggested_trans', '')
                ).strip()
                
                if not new_trans:
                    new_trans = term.get('suggested_trans', '')
                
                # 获取修改理由（使用当前循环的剩余时间）
                current_remaining = total_timeout - (time.time() - loop_start_time)
                if current_remaining <= 0:
                    print("时间已到，自动完成审查...")
                    break
                
                new_reason = input_with_timeout(
                    f"修改理由（直接回车使用默认，剩余 {int(current_remaining)} 秒）: ",
                    timeout=current_remaining,
                    default="人工修订"
                ).strip()
                
                # 保存原始建议
                if "original_suggested_trans" not in term:
                    term["original_suggested_trans"] = term.get("suggested_trans", "")
                
                # 更新术语
                if new_trans != term.get('suggested_trans', ''):
                    term["suggested_trans"] = new_trans
                    term["rationale"] = new_reason or "人工修订"
                    term["human_modified"] = True
                    print(f"\n√ 已更新: {term['src']} -> {new_trans}")
                else:
                    print(f"\n未修改: {term['src']}")
                
                time.sleep(1)  # 短暂暂停让用户看到更新信息
            else:
                print(f"[WARNING] ID超出范围，请输入 1-{len(terms_to_review)}")
                time.sleep(1)
        except ValueError:
            print("[WARNING] 无效的输入，请输入数字ID或 'q' 完成审查")
            time.sleep(1)
    
    # 所有术语都已审查（默认接受或已修改）
    newly_reviewed = terms_to_review

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
            print(f"  ES更新统计: {es_result}")
        except Exception as e:
            print(f"  [WARNING] 更新到ES失败: {e}")
            print(f"  提示: 请确保Elasticsearch服务正在运行")
    
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
        print(f"\n  正在保存RAG数据备份...")
        backup_path = export_rag_data_to_file()
        if backup_path:
            print(f"  √ RAG备份已保存: {backup_path}")
    except Exception as e:
        print(f"  [WARNING] 保存RAG备份失败: {e}")
    
    # 合并已审查和新审查的术语
    final_reviewed = reviewed_terms + newly_reviewed
    
    print(f"\n√ 术语审查完成: {len(reviewed_terms)} 个已审查 + {len(newly_reviewed)} 个新审查 = {len(final_reviewed)} 个总计\n")
    return final_reviewed
