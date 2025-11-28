def select_generate_slots_node(state: State) -> State:
    """
    直前の回答が「わかりません」の場合は従来通り 70% 側（= slots_2 or skip）を強制。
    それ以外の場合は、設定 SLOT_SELECTION_MODE に応じて
      - "random": 70/30 ランダム
      - "llm": LLM に遷移先ノードを決めさせる
    """
    new_state = copy.deepcopy(state)
    new_state["slot_generation_count"] = new_state.get("slot_generation_count", 0) + 1

    # 直近のインタビュー対象者の発話を取得
    last_interviewee_utternace = None
    for message in reversed(new_state["dialogue_history"]):
        if message.startswith("インタビュー対象者:"):
            last_interviewee_utternace = message
            break

    pac = (
        new_state.get("persona_attribute_candidates") or []
    )  # 候補リスト（なければ空）

    def choose_slots_2_or_skip():
        if not pac:
            new_state["branch"] = "skip_to_question"
        else:
            new_state["branch"] = "interviewer_llm_generate_slots_2"

    def choose_slots_deep():
        new_state["branch"] = "interviewer_llm_generate_slots"

    # ① 直前の回答が「わかりません」の場合 → 従来通り 70% 側を強制
    if last_interviewee_utternace and "わかりません" in last_interviewee_utternace:
        choose_slots_2_or_skip()
        return new_state

    # ② それ以外の場合：モードに応じて分岐
    if SLOT_SELECTION_MODE == "llm":
        # LLM に決めさせる
        branch = decide_next_branch_by_llm(new_state)

        # persona_attribute_candidates が空なのに slots_2 が選ばれた場合は skip にフォールバック
        if branch == "interviewer_llm_generate_slots_2" and not pac:
            new_state["branch"] = "skip_to_question"
        else:
            new_state["branch"] = branch
    else:
        # 従来のランダムロジック (デフォルト)
        if random.random() < 0.7:
            choose_slots_2_or_skip()
        else:
            choose_slots_deep()

    return new_state
