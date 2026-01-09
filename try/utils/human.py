def review_glossary(auto_glossary: list[dict]) -> list[dict]:
    print("\n====== 🛑 进入人工术语审查阶段 ======\n")

    reviewed = []

    for i, term in enumerate(auto_glossary, 1):
        print(f"[{i}] 原词: {term['src']}")
        print(f"    当前译名: {term['suggested_trans']}")
        print(f"    类型: {term.get('type')}")
        print(f"    理由: {term.get('rationale')}\n")

        action = input(
            "操作: [Enter=接受 | e=编辑 | d=删除] > "
        ).strip().lower()

        if action == "":
            reviewed.append(term)

        elif action == "e":
            new_trans = input("👉 新译名: ").strip()
            new_reason = input("👉 修改理由: ").strip()

            term["suggested_trans"] = new_trans
            term["rationale"] = new_reason or "人工修订"

            reviewed.append(term)

        elif action == "d":
            print("❌ 已删除该术语\n")
            continue

        else:
            print("⚠️ 无效操作，默认接受\n")
            reviewed.append(term)

        print("-" * 40)

    print("\n✅ 术语审查完成\n")
    return reviewed
