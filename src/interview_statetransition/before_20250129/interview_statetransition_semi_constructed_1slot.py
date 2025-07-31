# nohup python src/interview_statetransition/interview_statetransition_semi_constructed_1slot.py > out/log/output_$(date +%Y%m%d_%H%M%S).log 2>&1 &

# 半構造化インタビューを行うプログラム

# --------------------------------------------------------------------------------------------------------------------------------------------
# 設定セクション
# --------------------------------------------------------------------------------------------------------------------------------------------

# モデルの設定
MODEL_NAME = "gpt-4o-2024-11-20"
TEMPERATURE = 0.1

# 待機時間
WAIT_TIME = 3

# プロンプトの設定
PROMPT_IDLE_TALK_PATH = (
    "/mnt/work/interview/data/hashimoto-nakano/prompt_semi_const/prompt_idle_talk.txt"
)
PROMPT_FILL_SLOTS_PATH = (
    "/mnt/work/interview/data/hashimoto-nakano/prompt_semi_const/prompt_fill_slots.txt"
)
PROMPT_GENERATE_SLOTS_PATH = "/mnt/work/interview/data/hashimoto-nakano/prompt_semi_const/prompt_generate_slots.txt"
PROMPT_GENERATE_QUESTIONS_PATH = "/mnt/work/interview/data/hashimoto-nakano/prompt_semi_const/prompt_generating_question.txt"
PROMPT_USER_SIMULATOR_PATH = "/mnt/work/interview/data/hashimoto-nakano/prompt_semi_const/prompt_user_simulator.txt"
PROMPT_CAREER_TOPIC_PATH = "/mnt/work/interview/data/hashimoto-nakano/prompt_semi_const/prompt_career_topic.txt"
PROMPT_END_CONVERSATION_PATH = "/mnt/work/interview/data/hashimoto-nakano/prompt_semi_const/prompt_end_conversation.txt"

# ユーザシミュレータのpersona設定
PERSONA_SETTINGS_PATH = (
    "/mnt/work/interview/data/hashimoto-nakano/persona_settings/endo_p.txt"
)

# 自己評価アンケート
SELF_EVALUATION_PATH = (
    "/mnt/work/interview/data/hashimoto-nakano/questionnaire/endo_q.json"
)

# INTERVIEW_CONFIG（初期状態）の定義
# "value":\s*"[^"]*"   でスロットの値を抽出
# "value": None        でスロットの値を初期化
INTERVIEW_CONFIG = {
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
    "max_total_count": None,
    "slots": {"現在のキャリア": {"category": "キャリア", "value": None}},
}


# --------------------------------------------------------------------------------------------------------------------------------------------


import os
import json
import datetime
import time
import requests
import copy
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.output_parsers import PydanticOutputParser
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from typing import Dict, List, Optional
from typing_extensions import TypedDict
from icecream import ic
from pytz import timezone
from pydantic import BaseModel, Field, RootModel

# 必要な環境変数を設定
os.environ["LANGCHAIN_TRACING_V2"] = "false"


# ic.enable()
# ic.disable()

# デバッグ出力のフォーマットを設定
# ic.configureOutput(includeContext=True)

# モデルの定義
model = ChatOpenAI(
    model_name=MODEL_NAME,
    temperature=TEMPERATURE,
)

# model = ChatGoogleGenerativeAI(
#     model="gemini-1.5-flash-002",
#     temperature=TEMPERATURE,
# )


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
prompt_idle_talk = load_file(PROMPT_IDLE_TALK_PATH)

# スロットを埋めるプロンプト
prompt_fill_slots = load_file(PROMPT_FILL_SLOTS_PATH)

# スロットを生成するプロンプト
prompt_generate_slots = load_file(PROMPT_GENERATE_SLOTS_PATH)

# スロットから質問を生成するプロンプト
prompt_generate_questions = load_file(PROMPT_GENERATE_QUESTIONS_PATH)

# ユーザシミュレータのプロンプト
prompt_user_simulator = load_file(PROMPT_USER_SIMULATOR_PATH)

# キャリアの話題が出たかどうかを判定するプロンプト
prompt_career_topic = load_file(PROMPT_CAREER_TOPIC_PATH)

# 会話を終了するかどうかを判定するプロンプト
prompt_end_conversation = load_file(PROMPT_END_CONVERSATION_PATH)

# ユーザシミュレータのpersona設定
persona_settings = load_file(PERSONA_SETTINGS_PATH)

# 自己評価アンケート
self_evaluation = load_file(SELF_EVALUATION_PATH)


# interview_config（初期状態）の定義
interview_config = copy.deepcopy(INTERVIEW_CONFIG)


class SpeakCount(TypedDict):
    total_count: int
    interviewer_count: int
    interviewee_count: int
    interviewer_idle_talk_count: int
    interviewee_idle_talk_count: int
    interviewer_generate_question_count: int
    interviewee_generate_answer_count: int


class State(TypedDict):
    """
    State：ノード間の遷移の際に保存される情報
    各ノードが参照、更新する

    Attributes:
        dialogue_history(List[str]): インタビューの対話履歴
        speak_count(SpeakCount): 発言回数
        max_total_count(int): 最大ターン数
        slots(Dict): スロット情報
    """

    dialogue_history: List[str]
    speak_count: SpeakCount
    max_total_count: Optional[int]
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


# 保存フォルダの作成
def create_output_folder(base_folder="out/"):
    folder_path = os.path.join(base_folder, timestamp)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path


# 保存するデータの初期化
execution_folder = create_output_folder()
info_path = os.path.join(execution_folder, "info.json")
graph_image_path = os.path.join(execution_folder, "graph.png")
readme_path = os.path.join(execution_folder, "README.md")

# 空の情報を保存
with open(info_path, "w", encoding="utf-8-sig") as f:
    json.dump({}, f, indent=4, ensure_ascii=False)
with open(readme_path, "w", encoding="utf-8-sig") as f:
    f.write(f"Endo\nスロット引き継ぎあり\n初期スロット1つだけ")


# 保存される情報
execution_info = {
    "execution_time": formatted_timestamp,
    "command": __file__ if "__file__" in globals() else "<interactive>",
    "model_info": str(model),
    "persona_settings": persona_settings,
    "self_evaluation": self_evaluation,
    "interview_info": {
        "dialogue_history": interview_config["dialogue_history"],
        "speak_count": interview_config["speak_count"],
        "max_total_count": interview_config["max_total_count"],
        "slots": interview_config["slots"],
    },
    "new_state": {},
}


# 情報を保存する関数
def save_state_to_file(state: State, file_path: str):
    """
    現在の状態をファイルに保存する関数

    Args:
        state(State): 状態情報
        file_path(str): 保存先のファイルパス
    """
    execution_info["new_state"].update(state)

    try:
        with open(file_path, "w", encoding="utf-8-sig") as f:
            json.dump(execution_info, f, indent=4, ensure_ascii=False)
        print(f"!!状態を保存しました!!: {file_path}")
    except Exception as e:
        print(f"!!状態の保存に失敗しました!!: {e}")


save_state_to_file(interview_config, info_path)


def send_line_notify(notification_message):
    """
    LINEに通知する
    """
    line_notify_token = os.environ['LINE_TOKEN']
    line_notify_api = 'https://notify-api.line.me/api/notify'
    headers = {'Authorization': f'Bearer {line_notify_token}'}
    data = {'message': f'message: {notification_message}'}
    requests.post(line_notify_api, headers=headers, data=data)


# ========================================
# -----ノードの定義-----
# ========================================


def interviewer_llm_idle_talk(state: State):
    """
    interviewer_llm_idle_talk: インタビュアーの雑談を生成する関数

    Args:
        state(State): 状態情報
    Returns:
        Dict: 更新された状態情報(インタビュアーの発言, 発言回数)
    """
    time.sleep(WAIT_TIME)
    new_state = copy.deepcopy(state)

    dialogue_history = new_state["dialogue_history"]
    sc = new_state["speak_count"]

    template = prompt_idle_talk
    prompt = PromptTemplate(
        template=template,
        input_variables=["dialogue_history_str", "self_evaluation_str"],
    )

    dialogue_history_str = "\n".join(dialogue_history)
    system_message = prompt.format(
        dialogue_history_str=dialogue_history_str,
        self_evaluation_str=self_evaluation,
    )

    human_message = "\n発言を生成してください。\nインタビュアー: "

    print(
        f"\n\n===============関数interviewer_llm_idle_talk===============\nSystemMessage=\n{system_message}\nHumanMessage=\n{human_message}\n"
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

    print(f"new_dialogue: {new_dialogue}\n")

    # 発言回数を更新
    sc["total_count"] += 1
    sc["interviewer_count"] += 1
    sc["interviewer_idle_talk_count"] += 1

    new_state["dialogue_history"] = dialogue_history + [new_dialogue]
    new_state["speak_count"] = sc

    print(f"new_state: {new_state}\n")

    now = datetime.datetime.now(jst)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    node_name = "interviewer_llm_idle_talk"
    this_node_path = os.path.join(
        execution_folder, f"info_{timestamp}_{node_name}.json"
    )

    save_state_to_file(new_state, this_node_path)

    return new_state


# インタビュー対象者の雑談発話を生成する関数
def interviewee_llm_idle_talk(state: State):
    """
    interviewee_llm_idle_talk: インタビュー対象者の雑談を生成する関数

    Args:
        state(State): 状態情報
    Returns:
        Dict: 更新された状態情報(インタビュー対象者の発言, 発言回数)
    """
    time.sleep(WAIT_TIME)
    new_state = copy.deepcopy(state)

    dialogue_history = new_state["dialogue_history"]
    sc = new_state["speak_count"]

    template = prompt_user_simulator
    prompt = PromptTemplate(
        template=template,
        input_variables=[
            "persona_settings",
            "dialogue_history_str",
            "self_evaluation_str",
        ],
    )

    dialogue_history_str = "\n".join(dialogue_history)
    system_message = prompt.format(
        persona_settings=persona_settings,
        dialogue_history_str=dialogue_history_str,
        self_evaluation_str=self_evaluation,
    )

    human_message = "\n雑談発話を作成してください。\nインタビュー対象者: "

    print(
        f"\n\n===============関数interviewee_llm_idle_talk===============\nSystemMessage=\n{system_message}\nHumanMessage=\n{human_message}\n"
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

    print(f"new_dialogue: {new_dialogue}\n")

    # 発言回数を更新
    sc["total_count"] += 1
    sc["interviewee_count"] += 1
    sc["interviewee_idle_talk_count"] += 1

    new_state["dialogue_history"] = dialogue_history + [new_dialogue]
    new_state["speak_count"] = sc

    print(f"new_state: {new_state}\n")

    now = datetime.datetime.now(jst)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    node_name = "interviewee_llm_idle_talk"
    this_node_path = os.path.join(
        execution_folder, f"info_{timestamp}_{node_name}.json"
    )

    save_state_to_file(new_state, this_node_path)

    return new_state


def interviewer_llm_generate_question(state: State):
    """
    interviewer_llm_generate_question: インタビュアーの発言(質問)を生成する関数

    Args:
        state(State): 状態情報
    Returns:
        Dict: 更新された状態情報(インタビュアーの発言, 発言回数)
    """
    time.sleep(WAIT_TIME)
    new_state = copy.deepcopy(state)

    dialogue_history = new_state["dialogue_history"]
    sc = new_state["speak_count"]
    slots = new_state["slots"]

    template = prompt_generate_questions
    prompt = PromptTemplate(
        template=template,
        input_variables=[
            "dialogue_history_str",
            "current_slots",
            "self_evaluation_str",
        ],
        partial_variables={
            "format_instructions": question_output_parser.get_format_instructions()
        },
    )

    dialogue_history_str = "\n".join(dialogue_history)
    system_message = prompt.format(
        dialogue_history_str=dialogue_history_str,
        current_slots=slots,
        self_evaluation_str=self_evaluation,
    )

    human_message = "\n質問を生成してください。"

    print(
        f"\n\n===============関数interviewer_llm_generate_question===============\nSystemMessage=\n{system_message}\nHumanMessage=\n{human_message}\n"
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

                new_dialogue = f"インタビュアー: {question_text}"
                print(f"generated_question: {parsed_output}\n")

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

    print(f"new_dialogue: {new_dialogue}\n")

    # 発言回数を更新
    sc["total_count"] += 1
    sc["interviewer_count"] += 1
    sc["interviewer_generate_question_count"] += 1

    new_state["dialogue_history"] = dialogue_history + [new_dialogue]
    new_state["speak_count"] = sc

    print(f"new_state: {new_state}\n")

    now = datetime.datetime.now(jst)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    node_name = "interviewer_llm_generate_question"
    this_node_path = os.path.join(
        execution_folder, f"info_{timestamp}_{node_name}.json"
    )

    save_state_to_file(new_state, this_node_path)

    return new_state


# インタビュー対象者の発話(回答)を生成する関数
def interviewee_llm_generate_answer(state: State):
    """
    interviewee_llm_generate_answer: インタビュー対象者の発言(回答)を生成する関数

    Args:
        state(State): 状態情報
    Returns:
        Dict: 更新された状態情報(インタビュー対象者の発言, 発言回数)
    """
    time.sleep(WAIT_TIME)
    new_state = copy.deepcopy(state)

    dialogue_history = new_state["dialogue_history"]
    sc = new_state["speak_count"]

    template = prompt_user_simulator
    prompt = PromptTemplate(
        template=template,
        input_variables=[
            "persona_settings",
            "dialogue_history_str",
            "self_evaluation_str",
        ],
    )

    dialogue_history_str = "\n".join(dialogue_history)
    system_message = prompt.format(
        persona_settings=persona_settings,
        dialogue_history_str=dialogue_history_str,
        self_evaluation_str=self_evaluation,
    )

    human_message = "\n発話を生成してください。\nインタビュー対象者: "

    print(
        f"\n\n===============関数interviewee_llm_generate_answer===============\nSystemMessage=\n{system_message}\nHumanMessage=\n{human_message}\n"
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

    print(f"new_dialogue: {new_dialogue}\n")

    # 発言回数を更新
    sc["total_count"] += 1
    sc["interviewee_count"] += 1
    sc["interviewee_generate_answer_count"] += 1

    new_state["dialogue_history"] = dialogue_history + [new_dialogue]
    new_state["speak_count"] = sc

    print(f"new_state: {new_state}\n")

    now = datetime.datetime.now(jst)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    node_name = "interviewee_llm_generate_answer"
    this_node_path = os.path.join(
        execution_folder, f"info_{timestamp}_{node_name}.json"
    )

    save_state_to_file(new_state, this_node_path)

    return new_state


# スロットを埋める関数
def interviewer_llm_fill_slots(state: State):
    """
    interviewer_llm_fill_slots: インタビュアーがスロットを埋める関数

    Args:
        state(State): 状態情報
    Returns:
        Dict: 更新された状態情報(スロット情報)
    """
    time.sleep(WAIT_TIME)
    new_state = copy.deepcopy(state)

    dialogue_history = new_state["dialogue_history"]
    slots = new_state["slots"]

    template = prompt_fill_slots
    prompt = PromptTemplate(
        template=template,
        input_variables=[
            "dialogue_history_str",
            "current_slots",
            "self_evaluation_str",
        ],
        partial_variables={
            "format_instructions": slot_output_parser.get_format_instructions()
        },
    )

    dialogue_history_str = "\n".join(dialogue_history)
    system_message = prompt.format(
        dialogue_history_str=dialogue_history_str,
        current_slots=slots,
        self_evaluation_str=self_evaluation,
    )

    human_message = "\nスロットを埋めてください。"

    print(
        f"\n\n===============関数interviewer_llm_fill_slots===============\nSystemMessage=\n{system_message}\nHumanMessage=\n{human_message}\n"
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
                print(f"new_slots_dict: {new_slot_dict}\n")
                merged_slots = {**slots, **new_slot_dict}
            except Exception as e:
                print(f"Error occurred while decoding the JSON: {e}")
                merged_slots = slots
        else:
            merged_slots = slots

    except Exception as e:
        print(f"Error occurred while invoking the model: {e}")
        merged_slots = slots

    print(f"merged_slots: {merged_slots}\n")

    new_state["slots"] = merged_slots

    print(f"new_state: {new_state}\n")

    now = datetime.datetime.now(jst)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    node_name = "interviewer_llm_fill_slots"
    this_node_path = os.path.join(
        execution_folder, f"info_{timestamp}_{node_name}.json"
    )

    save_state_to_file(new_state, this_node_path)

    return new_state


# スロットを生成する関数
def interviewer_llm_generate_slots(state: State):
    """
    interviewer_llm_generate_slots: インタビュアーがスロットを生成する関数

    Args:
        state(State): 状態情報
    Returns:
        Dict: 更新された状態情報(スロット情報)
    """
    time.sleep(WAIT_TIME)
    new_state = copy.deepcopy(state)

    dialogue_history = new_state["dialogue_history"]
    slots = new_state["slots"]

    template = prompt_generate_slots
    prompt = PromptTemplate(
        template=template,
        input_variables=[
            "dialogue_history_str",
            "current_slots",
            "self_evaluation_str",
        ],
        partial_variables={
            "format_instructions": slot_output_parser.get_format_instructions()
        },
    )

    dialogue_history_str = "\n".join(dialogue_history)
    system_message = prompt.format(
        dialogue_history_str=dialogue_history_str,
        current_slots=slots,
        self_evaluation_str=self_evaluation,
    )

    human_message = "\nスロットを生成してください。"

    print(
        f"\n\n===============関数interviewer_llm_generate_slots===============\nSystemMessage=\n{system_message}\nHumanMessage=\n{human_message}\n"
    )

    try:
        response = model.invoke(
            [
                SystemMessage(content=system_message),
                HumanMessage(content=human_message),
            ]
        )
        if response and hasattr(response, "content"):
            content = response.content
            if content == "None":
                merged_slots = slots
            else:
                try:
                    new_slots_obj = slot_output_parser.parse(content)
                    new_slots_dict = {
                        slot_name: slot_model.dict()
                        for slot_name, slot_model in new_slots_obj.root.items()
                    }
                    print(f"new_slots_dict: {new_slots_dict}\n")
                    merged_slots = {**slots, **new_slots_dict}
                except Exception as e:
                    print(f"Error occurred while decoding the JSON: {e}")
                    merged_slots = slots
        else:
            merged_slots = slots

    except Exception as e:
        print(f"Error occurred while invoking the model: {e}")
        merged_slots = slots

    print(f"merged_slots: {merged_slots}\n")

    new_state["slots"] = merged_slots

    print(f"new_state: {new_state}\n")

    now = datetime.datetime.now(jst)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    node_name = "interviewer_llm_generate_slots"
    this_node_path = os.path.join(
        execution_folder, f"info_{timestamp}_{node_name}.json"
    )

    save_state_to_file(new_state, this_node_path)

    return new_state


# インタビュー終了時の処理
def end_interview(state: State):
    """
    end_interview: インタビューを終了する関数

    Args:
        state(State): 状態情報
    Returns:
        Dict: 更新された状態情報(インタビュー終了)
    """
    time.sleep(WAIT_TIME)
    new_state = copy.deepcopy(state)

    dialogue_history = new_state["dialogue_history"]
    sc = new_state["speak_count"]

    new_dialogue = (
        "インタビュアー: それでは、インタビューを終了します。ありがとうございました。"
    )

    # 発言回数を更新
    sc["total_count"] += 1
    sc["interviewer_count"] += 1
    sc["interviewer_generate_question_count"] += 1

    new_state["dialogue_history"] = dialogue_history + [new_dialogue]
    new_state["speak_count"] = sc

    print("\n\n===============関数end_interview===============\n")
    print(f"new_dialogue: {new_dialogue}\n")
    print(f"new_state: {new_state}\n")

    now = datetime.datetime.now(jst)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    node_name = "end_interview"
    this_node_path = os.path.join(
        execution_folder, f"info_{timestamp}_{node_name}.json"
    )

    save_state_to_file(new_state, this_node_path)
    save_state_to_file(new_state, info_path)

    return new_state


# ========================================
# -----条件分岐判定関数-----
# ========================================


# キャリアの話題が出たかどうかを判定する関数
def has_career_topic(state: State) -> bool:
    """
    has_career_topic: キャリアの話題が出たかどうかを判定する関数

    Args:
        state(State): 状態情報
    Returns:
        bool: キャリアの話題が出たかどうか
    """
    time.sleep(WAIT_TIME)
    new_state = copy.deepcopy(state)

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
        f"\n\n===============関数has_career_topic===============\nSystemMessage=\n{system_message}\nHumanMessage=\n{human_message}\n"
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

    print(f"has_career_topic: {has_career_topic}\n")

    now = datetime.datetime.now(jst)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    node_name = "has_career_topic"
    this_node_path = os.path.join(
        execution_folder, f"info_{timestamp}_{node_name}.json"
    )

    save_state_to_file(new_state, this_node_path)

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
    time.sleep(WAIT_TIME)
    new_state = copy.deepcopy(state)

    dialogue_history = new_state["dialogue_history"]
    max_total_count = new_state["max_total_count"]
    sc = new_state["speak_count"]
    total_count = sc["total_count"]
    current_slots = new_state["slots"]

    # 最大ターン数に達したら会話を終了
    if max_total_count is not None and total_count >= max_total_count:
        output = "end"
        return output

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
        f"\n\n===============関数finish_interview===============\nSystemMessage=\n{system_message}\nHumanMessage=\n{human_message}\n"
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

    print(f"output: {output}\n")

    now = datetime.datetime.now(jst)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    node_name = "finish_interview"
    this_node_path = os.path.join(
        execution_folder, f"info_{timestamp}_{node_name}.json"
    )

    save_state_to_file(new_state, this_node_path)

    return output


# -----状態遷移図の作成-----

# Graph（状態遷移図）の作成
graph_builder = StateGraph(State)

# ノードの追加
graph_builder.add_node("interviewer_llm_idle_talk", interviewer_llm_idle_talk)
graph_builder.add_node(
    "interviewer_llm_generate_question", interviewer_llm_generate_question
)
graph_builder.add_node("interviewer_llm_fill_slots", interviewer_llm_fill_slots)
graph_builder.add_node("interviewer_llm_generate_slots", interviewer_llm_generate_slots)
graph_builder.add_node("interviewee_llm_idle_talk", interviewee_llm_idle_talk)
graph_builder.add_node(
    "interviewee_llm_generate_answer", interviewee_llm_generate_answer
)
graph_builder.add_node("end_interview", end_interview)

# エッジの追加
# graph_builder.add_edge(START, "interviewer_start")
graph_builder.add_edge("interviewer_llm_idle_talk", "interviewee_llm_idle_talk")
graph_builder.add_conditional_edges(
    "interviewee_llm_idle_talk",
    has_career_topic,
    {
        True: "interviewer_llm_fill_slots",
        False: "interviewer_llm_idle_talk",
    },
)
graph_builder.add_conditional_edges(
    "interviewer_llm_fill_slots",
    finish_interview,
    {
        "end": "end_interview",
        "continue": "interviewer_llm_generate_slots",
    },
)
graph_builder.add_conditional_edges(
    "interviewer_llm_generate_slots",
    finish_interview,
    {
        "end": "end_interview",
        "continue": "interviewer_llm_generate_question",
    },
)

graph_builder.add_edge(
    "interviewer_llm_generate_question", "interviewee_llm_generate_answer"
)
graph_builder.add_edge("interviewee_llm_generate_answer", "interviewer_llm_fill_slots")
# graph_builder.add_edge("interviewer", END)


# Graphの始点を宣言
graph_builder.set_entry_point("interviewer_llm_idle_talk")

# Graphの終点を宣言
graph_builder.set_finish_point("end_interview")

# Graphのコンパイル
graph = graph_builder.compile()


# Graphの実行(引数にはStateの初期値を渡す)
new_state = graph.invoke(
    {
        "dialogue_history": interview_config["dialogue_history"],
        "speak_count": interview_config["speak_count"],
        "max_total_count": interview_config["max_total_count"],
        "slots": interview_config["slots"],
    },
    config={
        "recursion_limit": 200,
    },
    # debug=True,
)


# Graphの可視化
try:
    with open(graph_image_path, 'wb') as f:
        f.write(graph.get_graph(xray=True).draw_mermaid_png())
except Exception as e:
    print(f"Graphの可視化に失敗しました: {e}")

send_line_notify(
    f"インタビューが終了しました。結果は{execution_folder}に保存されました。"
)

print(f"インタビューが終了しました。結果は{execution_folder}に保存されました。")
