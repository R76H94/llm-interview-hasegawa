# python src/test.py > out/log/output_$(date +%Y%m%d_%H%M%S).log 2>&1

# 入出力テスト

import os
import json
import datetime
import operator
import copy
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from typing import Dict, TypedDict, List, Annotated, NotRequired, Optional
from langgraph.graph import StateGraph, START, END
from icecream import ic
from pytz import timezone
from pydantic import BaseModel, Field, RootModel
from langchain.output_parsers import PydanticOutputParser

# ic.enable()
ic.disable()


# model = ChatOpenAI(
#     model_name="gpt-4o-2024-11-20",
#     temperature=0.1,
# )

model = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash-002",
    temperature=0.1,
)


def load_file(file_path: str) -> str:
    """
    ファイルから情報を読み込む関数

    Args:
        file_path(str): ファイルパス
    Returns:
        str: ファイルの内容
    """
    with open(file_path, "r", encoding="utf-8-sig") as f:
        return f.read()


# 雑談を行うプロンプト
prompt_idle_talk = load_file(
    "/mnt/work/interview/data/hashimoto-nakano/prompt/prompt_idle_talk.txt"
)
ic(prompt_idle_talk)

# スロットを埋めるプロンプト
prompt_fill_slots = load_file(
    "/mnt/work/interview/data/hashimoto-nakano/prompt/prompt_fill_slots.txt"
)
ic(prompt_fill_slots)

# スロットを生成するプロンプト
prompt_generate_slots = load_file(
    "/mnt/work/interview/data/hashimoto-nakano/prompt/prompt_generate_slots.txt"
)
ic(prompt_generate_slots)

# スロットから質問を生成するプロンプト
prompt_generate_questions = load_file(
    "/mnt/work/interview/data/hashimoto-nakano/prompt/prompt_generating_question.txt"
)
ic(prompt_generate_questions)

# ユーザシミュレータのプロンプト
prompt_user_simulator = load_file(
    "/mnt/work/interview/data/hashimoto-nakano/prompt/prompt_user_simulator.txt"
)
ic(prompt_user_simulator)

# キャリアの話題が出たかどうかを判定するプロンプト
prompt_career_topic = load_file(
    "/mnt/work/interview/data/hashimoto-nakano/prompt/prompt_career_topic.txt"
)
ic(prompt_career_topic)

# 会話を終了するかどうかを判定するプロンプト
prompt_end_conversation = load_file(
    "/mnt/work/interview/data/hashimoto-nakano/prompt/prompt_end_conversation.txt"
)
ic(prompt_end_conversation)

# ユーザシミュレータのpersona設定
persona_settings = load_file(
    "/mnt/work/interview/data/hashimoto-nakano/persona_settings/endo_p.txt"
)
ic(persona_settings)


# interview_config（初期状態）の定義
interview_config = {
    "dialogue_history": [],
    "speak_count": {
        "total_count": 0,
        "interviewer_count": 0,
        "interviewee_count": 0,
        "interviewer_idle_talk_count": 0,
        "interviewee_idle_talk_count": 0,
        "interviewer_generate_question_count": 0,
        "interviewee_generate_answer_count": 0,
    },
    "max_turns": None,
    "slots": {
        "キャリア関連で最初に出た話題": {
            "category": "キャリア",
            "value": None,
        }
    },
}


class SpeakCount(TypedDict):
    total_count: int
    interviewer_count: int
    interviewee_count: int
    interviewer_idle_talk_count: int
    interviewee_idle_talk_count: int
    interviewer_generate_question_count: int
    interviewee_generate_answer_count: int


class State(TypedDict):
    dialogue_history: List[str]
    speak_count: SpeakCount
    max_turns: NotRequired[int]
    slots: Dict


class Slot(BaseModel):
    category: str = Field(..., title="スロットのカテゴリ")
    value: Optional[str] = Field(None, title="スロットの値")


class SlotDict(RootModel[Dict[str, Slot]]):
    pass


slot_output_parser = PydanticOutputParser(pydantic_object=SlotDict)


class TargetSlot(BaseModel):
    category: str = Field(..., title="スロットのカテゴリ")
    value: Optional[str] = Field(None, title="スロットの値")


class QuestionOutput(BaseModel):
    TargetSlot_S: Dict[str, TargetSlot] = Field(..., title="スロット")
    Question: str = Field(..., title="質問")


question_output_parser = PydanticOutputParser(pydantic_object=QuestionOutput)


jst = timezone("Asia/Tokyo")
now = datetime.datetime.now(jst)
timestamp = now.strftime("%Y%m%d_%H%M%S")
formatted_timestamp = now.strftime("%Y/%m/%d %H:%M:%S")


def create_output_folder(base_folder="out/"):
    folder_path = os.path.join(base_folder, timestamp)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path


execution_folder = create_output_folder()
info_path = os.path.join(execution_folder, "info.json")
graph_image_path = os.path.join(execution_folder, "graph.png")
readme_path = os.path.join(execution_folder, "README.md")

with open(info_path, "w", encoding="utf-8-sig") as f:
    json.dump({}, f, indent=4, ensure_ascii=False)
with open(readme_path, "w", encoding="utf-8-sig") as f:
    f.write(f"")

execution_info = {
    "execution_time": formatted_timestamp,
    "command": __file__ if "__file__" in globals() else "<interactive>",
    "model_info": str(model),
    "interview_info": {
        "dialogue_history": interview_config["dialogue_history"],
        "speak_count": interview_config["speak_count"],
        "max_turns": interview_config["max_turns"],
        "slots": interview_config["slots"],
    },
    "new_state": {},
}


def save_state_to_file(state: State, file_path: str):
    ic(state)
    execution_info["new_state"].update(state)

    try:
        with open(file_path, "w", encoding="utf-8-sig") as f:
            json.dump(execution_info, f, indent=4, ensure_ascii=False)
        print(f"状態を保存しました: {file_path}")
    except Exception as e:
        print(f"状態の保存に失敗しました: {e}")


save_state_to_file(interview_config, info_path)

# ＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝
# 1つのファイルにノード実行結果をまとめるための関数を追加
# ＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝
merged_output_path = os.path.join(execution_folder, "merged_output.json")


def save_merged_output(node_name: str, new_state: Dict):
    """
    各ノードで得られた出力を1つのファイルにまとめて追記保存するための関数。
    node_name: 実行したノード名
    new_state: ノード実行後のStateの更新内容（差分など）
    """
    data_to_save = {
        "node_name": node_name,
        "time": datetime.datetime.now(jst).strftime("%Y%m%d_%H%M%S"),
        "new_state": new_state,
    }
    # 既存のJSONファイルを読み込み、リストに追記して再度保存する
    if os.path.exists(merged_output_path):
        with open(merged_output_path, "r", encoding="utf-8-sig") as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:
                existing_data = []
    else:
        existing_data = []
    existing_data.append(data_to_save)
    with open(merged_output_path, "w", encoding="utf-8-sig") as f:
        json.dump(existing_data, f, indent=4, ensure_ascii=False)


# ＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝
# 以下、各ノードの定義
# ＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝
def interviewer_llm_idle_talk(state: State):
    """
    interviewer_llm_idle_talk: インタビュアーの雑談を生成する関数

    Args:
        state(State): 状態情報
    Returns:
        Dict: 更新された状態情報(インタビュアーの発言, 発言回数)
    """
    new_state = copy.deepcopy(state)
    ic(new_state)
    dialogue_history = new_state["dialogue_history"]
    sc = new_state["speak_count"]

    template = prompt_idle_talk
    prompt = PromptTemplate(
        template=template,
        input_variables=["dialogue_history_str"],
    )

    dialogue_history_str = "\n".join(dialogue_history)
    system_message = prompt.format(dialogue_history_str=dialogue_history_str)

    human_message = "\n発言を生成してください。\nインタビュアー: "

    print(
        f"\n\n=====関数interviewer_llm_idle_talk=====\nSystemMessage=\n{system_message}\nHumanMessage=\n{human_message}\n\n"
    )

    try:
        response = model.invoke(
            [
                SystemMessage(content=system_message),
                HumanMessage(content=human_message),
            ]
        )
        if response and hasattr(response, "content"):
            new_dialogue = f"インタビュアー: {response.content}"
        else:
            new_dialogue = (
                "インタビュアー: モデルの呼び出しに失敗しました。再試行してください。"
            )

    except Exception as e:
        print(f"Error occurred while invoking the model: {e}")
        new_dialogue = (
            "インタビュアー: モデルの呼び出しに失敗しました。再試行してください。"
        )

    ic(new_dialogue)
    print(f"new_dialogue: {new_dialogue}\n=======\n")

    # 発言回数を更新
    sc["total_count"] += 1
    sc["interviewer_count"] += 1
    sc["interviewer_idle_talk_count"] += 1
    # 生成した new_state を返す部分だけ修正
    new_state["dialogue_history"] = dialogue_history + [new_dialogue]
    new_state["speak_count"] = sc
    # save_state_to_file(new_state, this_node_path) は残しても良いが、1ファイルにまとめたい場合はコメントアウトしてもOK
    save_merged_output("interviewer_llm_idle_talk", new_state)
    return new_state


def interviewee_llm_idle_talk(state: State):
    """
    interviewee_llm_idle_talk: インタビュー対象者の雑談を生成する関数

    Args:
        state(State): 状態情報
    Returns:
        Dict: 更新された状態情報(インタビュー対象者の発言, 発言回数)
    """
    new_state = copy.deepcopy(state)
    ic(new_state)
    dialogue_history = new_state["dialogue_history"]
    sc = new_state["speak_count"]

    template = prompt_user_simulator
    prompt = PromptTemplate(
        template=template,
        input_variables=["persona_settings", "dialogue_history_str"],
    )

    dialogue_history_str = "\n".join(dialogue_history)
    system_message = prompt.format(
        persona_settings=persona_settings,
        dialogue_history_str=dialogue_history_str,
    )

    human_message = "\n発話を作成してください。\nインタビュー対象者: "

    print(
        f"\n\n=====関数interviewee_llm_idle_talk=====\nSystemMessage=\n{system_message}\nHumanMessage=\n{human_message}\n\n"
    )

    try:
        response = model.invoke(
            [
                SystemMessage(content=system_message),
                HumanMessage(content=human_message),
            ]
        )
        if response and hasattr(response, "content"):
            new_dialogue = f"インタビュー対象者: {response.content}"
        else:
            new_dialogue = "インタビュー対象者: モデルの呼び出しに失敗しました。再試行してください。"

    except Exception as e:
        print(f"Error occurred while invoking the model: {e}")
        new_dialogue = (
            "インタビュー対象者: モデルの呼び出しに失敗しました。再試行してください。"
        )

    ic(new_dialogue)
    print(f"new_dialogue: {new_dialogue}\n=======\n")

    # 発言回数を更新
    sc["total_count"] += 1
    sc["interviewee_count"] += 1
    sc["interviewee_idle_talk_count"] += 1

    new_state["dialogue_history"] = dialogue_history + [new_dialogue]
    new_state["speak_count"] = sc

    save_merged_output("interviewee_llm_idle_talk", new_state)
    return new_state


def interviewer_llm_generate_question(state: State):
    """
    interviewer_llm_generate_question: インタビュアーの発言(質問)を生成する関数

    Args:
        state(State): 状態情報
    Returns:
        Dict: 更新された状態情報(インタビュアーの発言, 発言回数)
    """
    new_state = copy.deepcopy(state)
    ic(new_state)
    dialogue_history = new_state["dialogue_history"]
    sc = new_state["speak_count"]
    slots = new_state["slots"]

    template = prompt_generate_questions
    prompt = PromptTemplate(
        template=template,
        input_variables=["dialogue_history_str", "current_slots"],
        partial_variables={
            "format_instructions": question_output_parser.get_format_instructions()
        },
    )

    dialogue_history_str = "\n".join(dialogue_history)
    system_message = prompt.format(
        dialogue_history_str=dialogue_history_str,
        current_slots=slots,
    )

    human_message = "\n質問を生成してください。"

    print(
        f"\n\n=====関数interviewer_llm_generate_question=====\nSystemMessage=\n{system_message}\nHumanMessage=\n{human_message}\n\n"
    )

    try:
        response = model.invoke(
            [
                SystemMessage(content=system_message),
                HumanMessage(content=human_message),
            ]
        )
        if response and hasattr(response, "content"):
            try:
                parsed_output = question_output_parser.parse(response.content)
                question_text = parsed_output.Question

                save_merged_output(
                    "interviewer_llm_generate_question",
                    parsed_output.dict(),
                )

                new_dialogue = f"インタビュアー: {question_text}"
            except Exception as e:
                print(f"Error occurred while decoding the JSON: {e}")
                new_dialogue = "インタビュアー: モデルの呼び出しに失敗しました。再試行してください。"
        else:
            new_dialogue = (
                "インタビュアー: モデルの呼び出しに失敗しました。再試行してください。"
            )

    except Exception as e:
        print(f"Error occurred while invoking the model: {e}")
        new_dialogue = (
            "インタビュアー: モデルの呼び出しに失敗しました。再試行してください。"
        )

    ic(new_dialogue)
    print(f"new_dialogue: {new_dialogue}\n=======\n")

    # 発言回数を更新
    sc["total_count"] += 1
    sc["interviewer_count"] += 1
    sc["interviewer_generate_question_count"] += 1

    new_state["dialogue_history"] = dialogue_history + [new_dialogue]
    new_state["speak_count"] = sc

    save_merged_output("interviewer_llm_generate_question", new_state)
    return new_state


def interviewee_llm_generate_answer(state: State):
    """
    interviewee_llm_generate_answer: インタビュー対象者の発言(回答)を生成する関数

    Args:
        state(State): 状態情報
    Returns:
        Dict: 更新された状態情報(インタビュー対象者の発言, 発言回数)
    """
    new_state = copy.deepcopy(state)
    ic(new_state)
    dialogue_history = new_state["dialogue_history"]
    sc = new_state["speak_count"]

    template = prompt_user_simulator
    prompt = PromptTemplate(
        template=template,
        input_variables=["persona_settings", "dialogue_history_str"],
    )

    dialogue_history_str = "\n".join(dialogue_history)
    system_message = prompt.format(
        persona_settings=persona_settings,
        dialogue_history_str=dialogue_history_str,
    )

    human_message = "\n発話を生成してください。\nインタビュー対象者: "

    print(
        f"\n\n=====関数interviewee_llm_generate_answer=====\nSystemMessage=\n{system_message}\nHumanMessage=\n{human_message}\n\n"
    )

    try:
        response = model.invoke(
            [
                SystemMessage(content=system_message),
                HumanMessage(content=human_message),
            ]
        )
        if response and hasattr(response, "content"):
            new_dialogue = f"インタビュー対象者: {response.content}"
        else:
            new_dialogue = "インタビュー対象者: モデルの呼び出しに失敗しました。再試行してください。"

    except Exception as e:
        print(f"Error occurred while invoking the model: {e}")
        new_dialogue = (
            "インタビュー対象者: モデルの呼び出しに失敗しました。再試行してください。"
        )

    ic(new_dialogue)
    print(f"new_dialogue: {new_dialogue}\n=======\n")

    # 発言回数を更新
    sc["total_count"] += 1
    sc["interviewee_count"] += 1
    sc["interviewee_generate_answer_count"] += 1

    new_state["dialogue_history"] = dialogue_history + [new_dialogue]
    new_state["speak_count"] = sc

    save_merged_output("interviewee_llm_generate_answer", new_state)
    return new_state


def interviewer_llm_fill_slots(state: State):
    """
    interviewer_llm_fill_slots: インタビュアーがスロットを埋める関数

    Args:
        state(State): 状態情報
    Returns:
        Dict: 更新された状態情報(スロット情報)
    """
    new_state = copy.deepcopy(state)
    ic(new_state)
    dialogue_history = new_state["dialogue_history"]
    slots = new_state["slots"]

    template = prompt_fill_slots
    prompt = PromptTemplate(
        template=template,
        input_variables=["dialogue_history_str", "current_slots"],
        partial_variables={
            "format_instructions": slot_output_parser.get_format_instructions()
        },
    )

    dialogue_history_str = "\n".join(dialogue_history)
    system_message = prompt.format(
        dialogue_history_str=dialogue_history_str,
        current_slots=slots,
    )

    human_message = "\nスロットを埋めてください。"

    print(
        f"\n\n=====関数interviewer_llm_fill_slots=====\nSystemMessage=\n{system_message}\nHumanMessage=\n{human_message}\n\n"
    )

    try:
        response = model.invoke(
            [
                SystemMessage(content=system_message),
                HumanMessage(content=human_message),
            ]
        )
        if response and hasattr(response, "content"):
            try:
                new_slots_obj = slot_output_parser.parse(response.content)
                new_slot_dict = {
                    slot_name: slot_model.dict()
                    for slot_name, slot_model in new_slots_obj.root.items()
                }
                print(f"###############\nnew_slots_dict: {new_slot_dict}")
                merged_slots = {**slots, **new_slot_dict}
            except Exception as e:
                print(f"Error occurred while decoding the JSON: {e}")
                merged_slots = slots
        else:
            merged_slots = slots

    except Exception as e:
        print(f"Error occurred while invoking the model: {e}")
        merged_slots = slots

    ic(merged_slots)
    print(f"merged_slots: {merged_slots}\n=======\n")

    new_state["slots"] = merged_slots

    save_merged_output("interviewer_llm_fill_slots", new_state)
    return new_state


def interviewer_llm_generate_slots(state: State):
    """
    interviewer_llm_generate_slots: インタビュアーがスロットを生成する関数

    Args:
        state(State): 状態情報
    Returns:
        Dict: 更新された状態情報(スロット情報)
    """
    new_state = copy.deepcopy(state)
    ic(new_state)
    dialogue_history = new_state["dialogue_history"]
    slots = new_state["slots"]

    template = prompt_generate_slots
    prompt = PromptTemplate(
        template=template,
        input_variables=["dialogue_history_str", "current_slots"],
        partial_variables={
            "format_instructions": slot_output_parser.get_format_instructions()
        },
    )

    dialogue_history_str = "\n".join(dialogue_history)
    system_message = prompt.format(
        dialogue_history_str=dialogue_history_str,
        current_slots=slots,
    )

    human_message = "\nスロットを生成してください。"

    print(
        f"\n\n=====関数interviewer_llm_generate_slots=====\nSystemMessage=\n{system_message}\nHumanMessage=\n{human_message}\n\n"
    )

    try:
        response = model.invoke(
            [
                SystemMessage(content=system_message),
                HumanMessage(content=human_message),
            ]
        )
        if response and hasattr(response, "content"):
            try:
                new_slots_obj = slot_output_parser.parse(response.content)
                new_slots_dict = {
                    slot_name: slot_model.dict()
                    for slot_name, slot_model in new_slots_obj.root.items()
                }
                print(f"###############\nnew_slots_dict: {new_slots_dict}")
                merged_slots = {**slots, **new_slots_dict}
            except Exception as e:
                print(f"Error occurred while decoding the JSON: {e}")
                merged_slots = slots
        else:
            merged_slots = slots

    except Exception as e:
        print(f"Error occurred while invoking the model: {e}")
        merged_slots = slots

    ic(merged_slots)
    print(f"merged_slots: {merged_slots}\n=======\n")

    new_state["slots"] = merged_slots

    save_merged_output("interviewer_llm_generate_slots", new_state)
    return new_state


def end_interview(state: State):
    new_state = copy.deepcopy(state)
    ic(new_state)
    dialogue_history = new_state["dialogue_history"]
    sc = new_state["speak_count"]

    new_dialogue = (
        "インタビュアー: それでは、インタビューを終了します。ありがとうございました。"
    )

    sc["total_count"] += 1
    sc["interviewer_count"] += 1
    sc["interviewer_generate_question_count"] += 1
    new_state["dialogue_history"] = dialogue_history + [new_dialogue]
    new_state["speak_count"] = sc

    save_merged_output("end_interview", new_state)
    return new_state


# ＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝
# 条件分岐系関数もそのまま
# ＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝


# キャリアの話題が出たかどうかを判定する関数
def has_career_topic(state: State) -> bool:
    """
    has_career_topic: キャリアの話題が出たかどうかを判定する関数

    Args:
        state(State): 状態情報
    Returns:
        bool: キャリアの話題が出たかどうか
    """
    new_state = copy.deepcopy(state)
    ic(new_state)
    dialogue_history = new_state["dialogue_history"]

    # キャリアの話題が出たかどうかを判定
    template = prompt_career_topic
    prompt = PromptTemplate(
        template=template,
        input_variables=["dialogue_history_str"],
    )

    dialogue_history_str = "\n".join(dialogue_history)
    system_message = prompt.format(dialogue_history_str=dialogue_history_str)

    human_message = "\n話題が出たかどうかを判定してください。\n判定: "

    print(
        f"\n\n=====関数has_career_topic=====\nSystemMessage=\n{system_message}\nHumanMessage=\n{human_message}\n\n"
    )

    try:
        response = model.invoke(
            [
                SystemMessage(content=system_message),
                HumanMessage(content=human_message),
            ]
        )
        if response and hasattr(response, "content"):
            # str型からbool型に変換(大文字小文字を無視)
            content = response.content.strip().lower()
            if content == "true":
                has_career_topic = True
            elif content == "false":
                has_career_topic = False
            else:
                # 判定が不明な場合はFalseとする
                print(f"トピック話題判定が不明です: {content}")
                has_career_topic = False
        else:
            has_career_topic = False

    except Exception as e:
        print(f"Error occurred while invoking the model: {e}")
        has_career_topic = False

    ic(has_career_topic)
    print(f"has_career_topic: {has_career_topic}\n=======\n")

    save_merged_output("has_career_topic", {"has_career_topic": has_career_topic})

    return has_career_topic


# 対話の終了を判断する関数
def finish_interview(state: State) -> str:
    """
    finish_interview: 対話の終了を判断する関数

    Args:
        state(State): 状態情報
    Returns:
        str: 対話の終了条件
    """
    new_state = copy.deepcopy(state)
    ic(new_state)
    dialogue_history = new_state["dialogue_history"]
    max_turns = new_state["max_turns"]
    sc = new_state["speak_count"]
    total_count = sc["total_count"]
    current_slots = new_state["slots"]

    # 最大ターン数に達したら会話を終了
    if max_turns is not None and total_count >= max_turns:
        output = "end"

    # 会話を続けるかどうかを判定
    template = prompt_end_conversation
    prompt = PromptTemplate(
        template=template,
        input_variables=["dialogue_history_str", "current_slots"],
    )

    dialogue_history_str = "\n".join(dialogue_history)
    system_message = prompt.format(
        dialogue_history_str=dialogue_history_str, current_slots=current_slots
    )

    human_message = "\n会話を続けるかどうかを判定してください。\n判定: "

    print(
        f"\n\n=====関数finish_interview=====\nSystemMessage=\n{system_message}\nHumanMessage=\n{human_message}\n\n"
    )

    try:
        response = model.invoke(
            [
                SystemMessage(content=system_message),
                HumanMessage(content=human_message),
            ]
        )
        if response and hasattr(response, "content"):
            # str型(大文字小文字を無視)
            content = response.content.strip().lower()
            if content == "end":
                output = "end"
            else:
                output = "continue"
        else:
            output = "continue"

    except Exception as e:
        print(f"Error occurred while invoking the model: {e}")
        output = "continue"

    ic(output)
    print(f"output: {output}\n=======\n")

    save_merged_output("finish_interview", {"output": output})

    return output


# ＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝
# グラフ構築部分は本番用。
# 今回は「ノードが正しく動くかテストしたい」ので、一旦コメントアウトでもOK
# ＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝
# graph_builder = StateGraph(State)
# ... (略)
# graph = graph_builder.compile()
# ... (略)


# ＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝
# 2. 「各ノードを1回ずつ呼び出してテストする」ための関数を作成
# ＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝
def test_run_nodes_once():
    # 初期状態を準備
    state: State = {
        "dialogue_history": [],
        "speak_count": {
            "total_count": 0,
            "interviewer_count": 0,
            "interviewee_count": 0,
            "interviewer_idle_talk_count": 0,
            "interviewee_idle_talk_count": 0,
            "interviewer_generate_question_count": 0,
            "interviewee_generate_answer_count": 0,
        },
        "slots": {},
        "max_turns": None,
    }
    print("===== テスト実行開始 =====")

    # 1. interviewer_llm_idle_talk を呼び出す
    state = interviewer_llm_idle_talk(state)

    # 2. interviewee_llm_idle_talk を呼び出す
    state = interviewee_llm_idle_talk(state)

    # 3. career_topic を呼び出す
    career = has_career_topic(state)

    # 4. interviewer_llm_generate_slots を呼び出す
    state = interviewer_llm_generate_slots(state)

    # 5. interviewer_llm_fill_slots を呼び出す
    state = interviewer_llm_fill_slots(state)

    # 6. finish_interview を呼び出す
    finish = finish_interview(state)

    # 5. interviewer_llm_generate_question を呼び出す
    state = interviewer_llm_generate_question(state)

    # 6. interviewee_llm_generate_answer を呼び出す
    state = interviewee_llm_generate_answer(state)

    # 7. end_interview を呼び出す
    state = end_interview(state)

    print("===== テスト実行終了 =====")
    print(f"すべてのノード出力は {merged_output_path} に追記されています。")


# ＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝
# 実際にテスト実行を呼び出す場合は以下を有効化
# ＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝
if __name__ == "__main__":
    test_run_nodes_once()
