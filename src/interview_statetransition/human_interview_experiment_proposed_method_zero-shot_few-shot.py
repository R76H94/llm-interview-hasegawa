# nohup python -m src.interview_statetransition.human_interview_experiment > out/log/output_$(date +%Y%m%d_%H%M%S).log 2>&1 &

# 対話実験の実行時は
# python -m src.interview_statetransition.human_interview_experiment_proposed_method_zero-shot_few-shot 2>&1 | tee -a out/log/$(TZ=Asia/Tokyo date +%Y%m%d_%H%M%S)_output.log


# 半構造化インタビューを行うプログラム

import os
import json
import datetime
import time
import requests
import copy
import random
import sys
from pathlib import Path
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.output_parsers import PydanticOutputParser
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from typing import Dict, List, Optional, Set
from typing_extensions import TypedDict
from icecream import ic
from pytz import timezone
from pydantic import BaseModel, Field, RootModel
from .config import load_config

cfg = load_config()

# --------------------------------------------------------------------------------------------------------------------------------------------
# 設定セクション
# --------------------------------------------------------------------------------------------------------------------------------------------

# モデルの設定
MODEL_NAME = cfg.model.name
TEMPERATURE = cfg.model.temperature

# 待機時間
WAIT_TIME = cfg.run.wait_time

# 出力ディレクトリ
OUT_DIR = cfg.run.out_dir

# 質問生成に使用したスロットを、スロット埋めに使用するかどうか
USE_QUESTION_SLOT_IN_FILL_SLOTS = cfg.interview.use_question_slot_in_fill_slots

# スロット選択モード ("random" or "llm")
SLOT_SELECTION_MODE = cfg.interview.slot_selection_mode

# 話題順制御モード ("record", "replay", "free")
TOPIC_MODE = cfg.interview.topic_mode
TOPIC_ORDER_FILE = cfg.interview.topic_order_file

# プロンプトの設定
PROMPT_FILL_SLOTS_PATH = cfg.paths.prompts.fill_slots
PROMPT_GENERATE_SLOTS_PATH = cfg.paths.prompts.generate_slots
PROMPT_GENERATE_SLOTS_2_PATH = cfg.paths.prompts.generate_slots_2
PROMPT_GENERATE_QUESTIONS_PATH = cfg.paths.prompts.generate_questions
PROMPT_USER_SIMULATOR_PATH = cfg.paths.prompts.user_simulator
PROMPT_END_CONVERSATION_PATH = cfg.paths.prompts.end_conversation
PROMPT_ESTIMATE_PERSONA_PATH = cfg.paths.prompts.estimate_persona
PROMPT_FUKABORI_QUESTIONS_PATH = cfg.paths.prompts.fukabori_questions

# ユーザシミュレータのpersona設定
PERSONA_SETTINGS_PATH = cfg.paths.persona_settings


# INTERVIEW_CONFIG（初期状態）の定義
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
    "max_total_count": cfg.interview.max_total_count,
    "min_total_count": cfg.interview.min_total_count,
    "estimate_persona": cfg.interview.estimate_persona,
    "persona_attribute_candidates": cfg.interview.persona_attribute_candidates,
    "slots": cfg.interview.slots,
    "slot_generation_count": 0,
    "branch": None,
    "last_generated_slot": [],
    "last_question_target_slot": {},
    "topic_sequence": [],  # 話題順を記録
    "topic_replay_index": 0,  # 再生時のインデックス
    "current_topic": None,  # 現在の話題
}

# --------------------------------------------------------------------------------------------------------------------------------------------


# 必要な環境変数を設定
os.environ["LANGCHAIN_TRACING_V2"] = "false"


ic.enable()
# デバッグ出力のフォーマットを設定
ic.configureOutput(includeContext=True)

# ic.disable()


# モデルの定義
if cfg.model.provider == "openai":
    model = ChatOpenAI(
        model=cfg.model.name,
        temperature=cfg.model.temperature,
    )
elif cfg.model.provider == "google":
    model = ChatGoogleGenerativeAI(
        model=cfg.model.name,
        temperature=cfg.model.temperature,
    )
else:
    raise ValueError(f"Unknown model provider: {cfg.model.provider}")

# random.seed(42)


def load_file(file_path: str) -> str:
    """
    ファイルから情報を読み込む関数
    読み込みに失敗した場合、プログラムを終了する

    Args:
        file_path(str): ファイルパス
    Returns:
        str: ファイルの内容
    """
    if not os.path.exists(file_path):
        print(f"ファイルが存在しません: {file_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            return f.read()
    except Exception as e:
        print(
            f"ファイルの読み込みに失敗しました: {file_path}, エラー: {e}",
            file=sys.stderr,
        )
        sys.exit(1)


def load_topic_order(file_path: str) -> List[Dict]:
    """
    話題順ファイルを読み込む関数

    Args:
        file_path(str): 話題順ファイルのパス
    Returns:
        List[Dict]: 話題順のリスト
    """
    if not os.path.exists(file_path):
        print(f"話題順ファイルが存在しません: {file_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
            return data.get("topic_sequence", [])
    except Exception as e:
        print(
            f"話題順ファイルの読み込みに失敗しました: {file_path}, エラー: {e}",
            file=sys.stderr,
        )
        sys.exit(1)


def save_topic_order(topic_sequence: List[Dict], file_path: str):
    """
    話題順をファイルに保存する関数

    Args:
        topic_sequence(List[Dict]): 話題順のリスト
        file_path(str): 保存先のファイルパス
    """
    jst = timezone("Asia/Tokyo")
    now = datetime.datetime.now(jst)

    data = {
        "execution_time": now.strftime("%Y/%m/%d %H:%M:%S"),
        "model": MODEL_NAME,
        "topic_mode": TOPIC_MODE,
        "topic_sequence": topic_sequence,
    }

    try:
        with open(file_path, "w", encoding="utf-8-sig") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"話題順を保存しました: {file_path}")
    except Exception as e:
        print(f"話題順の保存に失敗しました: {e}", file=sys.stderr)


def _is_tty_stdin() -> bool:
    try:
        return sys.stdin.isatty()
    except Exception:
        return False


def read_human_input(
    prompt_text: str, input_file: str | None, timeout_sec: int | None
) -> str:
    """人間の入力を取得する関数
    - TTYが利用可能な場合、標準入力から取得
    - TTYが利用できない場合、input_fileから取得
    - timeout_secが指定されている場合、タイムアウトを設定
    """
    deadline = time.time() + (timeout_sec or 10**9)

    # 1)対話実行
    if _is_tty_stdin() and input_file is None:
        try:
            return input(prompt_text).strip()
        except EOFError:
            return ""
    # 2)input_fileから取得
    if input_file:
        path = Path(input_file)
        print(f"[human-input] Waiting input in file: {path}", flush=True)
        while time.time() < deadline:
            if path.exists():
                try:
                    text = path.read_text(encoding="utf-8-sig").strip()
                except Exception:
                    text = ""
                if text:
                    # 1行目だけ消費する（複数行来たら残りは次回に使える）
                    lines = text.splitlines()
                    first, rest = lines[0].strip(), "\n".join(lines[1:])
                    try:
                        path.write_text(rest, encoding="utf-8-sig")
                    except Exception:
                        pass
                    return first
            time.sleep(1)
        return ""

    # 3) どちらも使えない場合
    print("[human-input] No TTY and no input_file configured.", flush=True)
    time.sleep(1)
    return ""


INTERVIEWEE_MODE = cfg.interviewee.mode
HUMAN_INPUT_FILE = cfg.interviewee.input_file
HUMAN_WAIT_SEC = cfg.interviewee.wait_human_sec

# スロットを埋めるプロンプト
prompt_fill_slots = load_file(PROMPT_FILL_SLOTS_PATH)

# スロットを生成するプロンプト
prompt_generate_slots = load_file(PROMPT_GENERATE_SLOTS_PATH)

# スロットを生成するプロンプト（2回目）
prompt_generate_slots_2 = load_file(PROMPT_GENERATE_SLOTS_2_PATH)

# スロットから質問を生成するプロンプト
prompt_generate_questions = load_file(PROMPT_GENERATE_QUESTIONS_PATH)

# ユーザシミュレータのプロンプト
prompt_user_simulator = load_file(PROMPT_USER_SIMULATOR_PATH)

# 会話を終了するかどうかを判定するプロンプト
prompt_end_conversation = load_file(PROMPT_END_CONVERSATION_PATH)

# ペルソナ情報を推定するプロンプト
prompt_estimate_persona = load_file(PROMPT_ESTIMATE_PERSONA_PATH)

# 深堀りLLMが深掘りするかどうかを決める際のプロンプト
prompt_fukabori_questions = load_file(PROMPT_FUKABORI_QUESTIONS_PATH)

# ユーザシミュレータのpersona設定
persona_settings = load_file(PERSONA_SETTINGS_PATH)

# interview_config（初期状態）の定義
interview_config = copy.deepcopy(INTERVIEW_CONFIG)

# 話題順の初期化
if TOPIC_MODE == "replay" and TOPIC_ORDER_FILE:
    # replay モードの場合、ファイルから話題順を読み込む
    loaded_topic_sequence = load_topic_order(TOPIC_ORDER_FILE)
    interview_config["topic_sequence"] = loaded_topic_sequence
    print(f"話題順を読み込みました: {len(loaded_topic_sequence)}件")
    print(f"話題順: {[item['selected_topic'] for item in loaded_topic_sequence]}")


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
    各ノードはこの情報を受け取り、必要に応じて更新する

    Attributes:
        dialogue_history(List[str]): インタビューの対話履歴
        speak_count(SpeakCount): 発言回数
        max_total_count(int): 最大ターン数
        min_total_count(int): 最小ターン数
        estimate_persona(Optional[str]): 推定されたペルソナ情報
        persona_attribute_candidates(List[str]): ペルソナ属性の候補
        slots(Dict): スロット情報
        slot_generation_count(int): スロット生成の関数が呼び出された回数
        branch(Optional[str]): 分岐情報
        last_generated_slot(List[str]): 生成された深堀りスロット
        topic_sequence(List[Dict]): 話題順を記録
        topic_replay_index(int): 再生時のインデックス
        current_topic(Optional[str]): 現在の話題
    """

    dialogue_history: List[str]
    speak_count: SpeakCount
    max_total_count: Optional[int]
    min_total_count: Optional[int]
    estimate_persona: Optional[str]
    persona_attribute_candidates: List[str]
    slots: Dict
    slot_generation_count: int
    branch: Optional[str]
    last_generated_slot: List[str]
    last_question_target_slot: Dict[str, Optional[str]]
    topic_sequence: List[Dict]
    topic_replay_index: int
    current_topic: Optional[str]


class SlotDict(RootModel[Dict[str, Optional[str]]]):
    pass


# スロットの出力をパースするためのパーサー
slot_output_parser = PydanticOutputParser(pydantic_object=SlotDict)


class QuestionOutput(BaseModel):
    Target_Slot: Dict[str, Optional[str]] = Field(..., title="スロット")
    Question: str = Field(..., title="質問")


# 質問の出力をパースするためのパーサー
question_output_parser = PydanticOutputParser(pydantic_object=QuestionOutput)


jst = timezone("Asia/Tokyo")
now = datetime.datetime.now(jst)
timestamp = now.strftime("%Y%m%d_%H%M%S")
formatted_timestamp = now.strftime("%Y/%m/%d %H:%M:%S")


# 保存フォルダの作成
# out/配下にtimestampのディレクトリを作成
def create_output_folder(base_folder=OUT_DIR) -> str:
    folder_path = os.path.join(base_folder, timestamp)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path


def append_final_config_to_readme(readme_path: str, cfg) -> None:
    p = Path(readme_path)

    cfg_json = json.dumps(cfg.model_dump(), indent=2, ensure_ascii=False)

    block = (
        "\n\n---\n" "## 実行時設定（最終確定値）\n" "```json\n" f"{cfg_json}\n" "```\n"
    )

    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8-sig") as f:
        f.write(block)


# 保存するデータの初期化
execution_folder = create_output_folder()
info_path = os.path.join(execution_folder, "info.json")
graph_image_path = os.path.join(execution_folder, "graph.png")
readme_path = os.path.join(execution_folder, "README.md")
topic_order_path = os.path.join(execution_folder, "topic_order.json")
log_path = os.path.join(execution_folder, f"output_{timestamp}.log")

# 空の情報を保存
with open(info_path, "w", encoding="utf-8-sig") as f:
    json.dump({}, f, indent=4, ensure_ascii=False)
with open(readme_path, "w", encoding="utf-8-sig") as f:
    f.write(
        f"- 開始時刻: {formatted_timestamp}\n- モデル: {MODEL_NAME}\n- ユーザシミュレータ: {PERSONA_SETTINGS_PATH}\n- 話題順モード: {TOPIC_MODE}\n"
    )
    if TOPIC_MODE == "replay" and TOPIC_ORDER_FILE:
        f.write(f"- 話題順ファイル: {TOPIC_ORDER_FILE}\n")

append_final_config_to_readme(readme_path, cfg)

# 保存される情報
execution_info = {
    "execution_time": formatted_timestamp,
    "command": __file__ if "__file__" in globals() else "<interactive>",
    "model_info": str(model),
    "persona_settings": persona_settings,
    "interview_info": interview_config,
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
    token = os.getenv("LINE_TOKEN")
    if not token:
        print("LINE_TOKEN未設定", file=sys.stderr)
        return
    try:
        requests.post(
            "https://notify-api.line.me/api/notify",
            headers={"Authorization": f"Bearer {token}"},
            data={"message": f"message: {notification_message}"},
            timeout=10,
        )
    except Exception as e:
        print(f"LINE通知に失敗しました: {e}", file=sys.stderr)
        return


def interviewer_llm_generate_question(state: State) -> State:
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
    pending = new_state.get("last_generated_slot", [])
    all_slots = new_state["slots"]
    estimate_persona = new_state["estimate_persona"]
    current_topic = new_state.get("current_topic", None)

    ic(pending)
    ic(all_slots)
    ic(estimate_persona)
    ic(current_topic)

    if pending:
        # 深掘りスロットを優先
        slots_for_prompt = {k: all_slots[k] for k in pending if k in all_slots}
    elif current_topic and current_topic in all_slots:
        # 記録した話題に完全一致するスロットがある場合
        slots_for_prompt = {current_topic: all_slots[current_topic]}
    else:
        # 全スロットからランダム選択
        shuffled_keys = random.sample(list(all_slots.keys()), k=len(all_slots))
        slots_for_prompt = {key: all_slots[key] for key in shuffled_keys}

    ic(slots_for_prompt)

    template = prompt_generate_questions
    prompt = PromptTemplate(
        template=template,
        input_variables=[
            "dialogue_history_str",
            "current_slots",
            "estimate_persona",
        ],
        partial_variables={
            "format_instructions": question_output_parser.get_format_instructions()
        },
    )

    dialogue_history_str = "\n".join(dialogue_history)
    system_message = prompt.format(
        dialogue_history_str=dialogue_history_str,
        current_slots=slots_for_prompt,
        estimate_persona=estimate_persona,
    )

    human_message = "出力:"

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
            print(f"generated_question: {response.content}\n")
            try:
                parsed_output = question_output_parser.parse(response.content)
                question_text = parsed_output.Question
                try:
                    target_slot_dict = parsed_output.Target_Slot or {}
                except Exception:
                    target_slot_dict = {}
                new_state["last_question_target_slot"] = dict(target_slot_dict)
                ic(new_state["last_question_target_slot"])
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

    if pending:
        new_state["last_generated_slot"] = []

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


def interviewee_llm_generate_answer_impl(state: State) -> str:
    template = prompt_user_simulator
    prompt = PromptTemplate(
        template=template,
        input_variables=["persona_settings", "dialogue_history_str"],
    )
    dialogue_history_str = "\n".join(state["dialogue_history"])
    system_message = prompt.format(
        persona_settings=persona_settings,
        dialogue_history_str=dialogue_history_str,
    )
    human_message = "インタビュー対象者:"
    print(
        f"\n\n===============関数interviewee_llm_generate_answer_impl===============\nSystemMessage=\n{system_message}\nHumanMessage=\n{human_message}\n"
    )

    response = model.invoke(
        [SystemMessage(content=system_message), HumanMessage(content=human_message)]
    )
    return (
        response.content
        if (response and hasattr(response, "content"))
        else "モデルの呼び出しに失敗しました。再試行してください。"
    )


def interviewee_human_generate_answer_impl(state: State) -> str:
    dh = "\n".join(state["dialogue_history"])
    prompt_text = f"\n[あなた=インタビュー対象者] 直近のやり取り:\n{dh}\n質問へのあなたの回答を1行で入力してください> "
    text = read_human_input(prompt_text, HUMAN_INPUT_FILE, HUMAN_WAIT_SEC)
    return text or "（無回答）"


def interviewee_llm_generate_answer(state: State) -> State:
    """既存関数名は維持。内部で LLM/HUMAN を分岐。"""
    time.sleep(WAIT_TIME)
    new_state = copy.deepcopy(state)
    sc = new_state["speak_count"]
    try:
        if INTERVIEWEE_MODE == "human":
            utter = interviewee_human_generate_answer_impl(new_state)
        else:
            utter = interviewee_llm_generate_answer_impl(new_state)
        new_dialogue = f"インタビュー対象者: {utter}"
    except Exception as e:
        print(f"Error in interviewee generate_answer: {e}")
        new_dialogue = "インタビュー対象者: （エラーにより無回答）"

    sc["total_count"] += 1
    sc["interviewee_count"] += 1
    sc["interviewee_generate_answer_count"] += 1
    new_state["dialogue_history"] = new_state["dialogue_history"] + [new_dialogue]
    new_state["speak_count"] = sc

    now = datetime.datetime.now(jst)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    node_name = "interviewee_llm_generate_answer"
    this_node_path = os.path.join(
        execution_folder, f"info_{timestamp}_{node_name}.json"
    )
    save_state_to_file(new_state, this_node_path)
    return new_state


# スロットを埋める関数
def interviewer_llm_fill_slots(state: State) -> State:
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

    if USE_QUESTION_SLOT_IN_FILL_SLOTS:
        target_slot_for_prompt = new_state.get("last_question_target_slot", {})
    else:
        target_slot_for_prompt = {}

    template = prompt_fill_slots
    prompt = PromptTemplate(
        template=template,
        input_variables=["dialogue_history_str", "current_slots", "target_slot"],
        partial_variables={
            "format_instructions": slot_output_parser.get_format_instructions()
        },
    )

    dialogue_history_str = "\n".join(dialogue_history)
    system_message = prompt.format(
        dialogue_history_str=dialogue_history_str,
        current_slots=slots,
        target_slot=target_slot_for_prompt,
    )

    human_message = "出力:"

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
            print(f"new_slots_dict: {response.content}\n")
            try:
                new_slots_obj = slot_output_parser.parse(response.content)
                new_slot_dicts = dict(new_slots_obj.root)
                merged_slots = {**slots, **new_slot_dicts}
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
def interviewer_llm_generate_slots(state: State) -> State:
    """
    interviewer_llm_generate_slots: インタビュアーがスロットを生成する関数
    深堀りスロットを生成する
    ※深堀りは各インタビューで独立なので、話題順の記録・再生対象外

    Args:
        state(State): 状態情報
    Returns:
        Dict: 更新された状態情報(スロット情報)
    """
    time.sleep(WAIT_TIME)
    new_state = copy.deepcopy(state)

    dialogue_history = new_state["dialogue_history"]
    slots = new_state["slots"]
    prev_keys = set(slots.keys())
    estimate_persona = new_state["estimate_persona"]

    template = prompt_generate_slots
    prompt = PromptTemplate(
        template=template,
        input_variables=[
            "dialogue_history_str",
            "current_slots",
            "estimate_persona",
        ],
        partial_variables={
            "format_instructions": slot_output_parser.get_format_instructions()
        },
    )

    dialogue_history_str = "\n".join(dialogue_history)
    system_message = prompt.format(
        dialogue_history_str=dialogue_history_str,
        current_slots=slots,
        estimate_persona=estimate_persona,
    )

    human_message = "出力:"

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
            print(f"new_slots_dict: {content}\n")
            if content == "None":
                merged_slots = slots
                added = []
            else:
                try:
                    new_slots_obj = slot_output_parser.parse(content)
                    new_slots_dict = dict(new_slots_obj.root)
                    merged_slots = {**slots, **new_slots_dict}
                    added = [k for k in merged_slots.keys() if k not in prev_keys]
                except Exception as e:
                    print(f"Error occurred while decoding the JSON: {e}")
                    merged_slots = slots
                    added = []
        else:
            merged_slots = slots
            added = []

    except Exception as e:
        print(f"Error occurred while invoking the model: {e}")
        merged_slots = slots
        added = []

    print(f"merged_slots: {merged_slots}\n")

    new_state["slots"] = merged_slots
    new_state["last_generated_slot"] = added

    print(f"new_state: {new_state}\n")

    now = datetime.datetime.now(jst)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    node_name = "interviewer_llm_generate_slots"
    this_node_path = os.path.join(
        execution_folder, f"info_{timestamp}_{node_name}.json"
    )

    save_state_to_file(new_state, this_node_path)

    return new_state


def interviewer_llm_generate_slots_2(state: State) -> State:
    """
    interviewer_llm_generate_slots_2: インタビュアーがスロットを生成する関数
    プールからランダムにトピックを選び、そのトピックに関連するスロットを生成する
    ※話題順の記録・再生対象

    Args:
        state(State): 状態情報
    Returns:
        Dict: 更新された状態情報(スロット情報)
    """
    time.sleep(WAIT_TIME)
    new_state = copy.deepcopy(state)

    dialogue_history = new_state["dialogue_history"]
    slots = new_state["slots"]
    prev_keys = set(slots.keys())
    pac = list(new_state.get("persona_attribute_candidates") or [])

    ic(prev_keys)
    ic(pac)

    # 話題順の記録・再生処理
    if TOPIC_MODE == "replay":
        # 再生モード: 事前に記録された話題順を使用
        topic_sequence = new_state.get("topic_sequence", [])
        replay_index = new_state.get("topic_replay_index", 0)

        ic(topic_sequence)
        ic(replay_index)

        if replay_index < len(topic_sequence):
            random_topic = topic_sequence[replay_index]["selected_topic"]
            new_state["topic_replay_index"] = replay_index + 1
            if random_topic in pac:
                pac.remove(random_topic)
            print(f"[REPLAY MODE] 話題を再生: {random_topic} (index: {replay_index})")
        else:
            # 記録された話題が終わった場合、通常動作に戻る
            if not pac:
                print(
                    f"[REPLAY MODE] 記録された話題が終わり、persona_attribute_candidatesも空です"
                )
                return new_state

            random_topic = random.choice(pac)
            pac.remove(random_topic)
            print(
                f"[REPLAY MODE] 記録された話題が終わったため、通常動作に戻りました: {random_topic}"
            )
    else:
        # record または free モード: ランダムに話題を選択
        if not pac:
            return new_state

        random_topic = random.choice(pac)
        pac.remove(random_topic)

        # record モードの場合、話題を記録
        if TOPIC_MODE == "record":
            topic_entry = {
                "step": new_state["slot_generation_count"] + 1,
                "selected_topic": random_topic,
                "slot_generation_count": new_state["slot_generation_count"],
            }
            new_state["topic_sequence"].append(topic_entry)
            print(f"[RECORD MODE] 話題を記録: {random_topic}")

    ic(random_topic)
    ic(pac)

    template = prompt_generate_slots_2
    prompt = PromptTemplate(
        template=template,
        input_variables=["dialogue_history_str", "current_slots", "topic"],
        partial_variables={
            "format_instructions": slot_output_parser.get_format_instructions()
        },
    )

    dialogue_history_str = "\n".join(dialogue_history)
    system_message = prompt.format(
        dialogue_history_str=dialogue_history_str,
        current_slots=slots,
        topic=random_topic,
    )

    human_message = "出力:"

    print(
        f"\n\n===============関数interviewer_llm_generate_slots_2===============\nSystemMessage=\n{system_message}\nHumanMessage=\n{human_message}\n"
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
            print(f"new_slots_dict: {content}\n")
            if content == "None":
                merged_slots = slots
                added = []
            else:
                try:
                    new_slots_obj = slot_output_parser.parse(content)
                    new_slots_dict = dict(new_slots_obj.root)
                    merged_slots = {**slots, **new_slots_dict}
                    added = [k for k in merged_slots.keys() if k not in prev_keys]
                except Exception as e:
                    print(f"Error occurred while decoding the JSON: {e}")
                    merged_slots = slots
                    added = []
        else:
            merged_slots = slots
            added = []

    except Exception as e:
        print(f"Error occurred while invoking the model: {e}")
        merged_slots = slots
        added = []

    print(f"merged_slots: {merged_slots}\n")

    new_state["persona_attribute_candidates"] = pac
    new_state["current_topic"] = random_topic
    new_state["slots"] = merged_slots
    new_state["last_generated_slot"] = added
    now = datetime.datetime.now(jst)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    node_name = "interviewer_llm_generate_slots_2"
    this_node_path = os.path.join(
        execution_folder, f"info_{timestamp}_{node_name}.json"
    )

    save_state_to_file(new_state, this_node_path)

    return new_state


# LLMにbranchを決めさせるための関数
def decide_next_branch_by_llm(state: State) -> str:
    """
    LLM に次の遷移先ノードを決めさせる。
    戻り値はいずれか:
        - "interviewer_llm_generate_slots"
        - "interviewer_llm_generate_slots_2"
        - "skip_to_question"
    想定外の出力の場合はフォールバックとしてランダム 70/30 を返す。
    """
    dialogue_history_str = "\n".join(state["dialogue_history"])
    current_slots = state["slots"]
    estimate_persona = state.get("estimate_persona")

    template = prompt_fukabori_questions
    prompt = PromptTemplate(
        template=template,
        input_variables=["dialogue_history_str", "current_slots", "estimate_persona"],
    )

    system_message = prompt.format(
        dialogue_history_str=dialogue_history_str,
        current_slots=current_slots,
        estimate_persona=estimate_persona,
    )
    human_message = "出力:"

    print(
        "\n\n===============関数_decide_next_branch_by_llm===============\n"
        f"SystemMessage=\n{system_message}\nHumanMessage=\n{human_message}\n"
    )

    try:
        response = model.invoke(
            [
                SystemMessage(content=system_message),
                HumanMessage(content=human_message),
            ]
        )
        if not (response and hasattr(response, "content")):
            raise ValueError("empty response")

        raw = response.content.strip().lower()
        print(f"LLM next-branch raw output: {raw}")

        # 想定される出力パターンを雑に吸収するマッピング
        if "generate_slots_2" in raw or "slots_2" in raw:
            return "interviewer_llm_generate_slots_2"
        if "generate_slots" in raw and "generate_slots_2" not in raw:
            return "interviewer_llm_generate_slots"
        if "skip" in raw or "question" in raw:
            return "skip_to_question"

        # 想定外 → 例外扱いしてフォールバックへ
        raise ValueError(f"unexpected content: {raw}")

    except Exception as e:
        print(f"Error in _decide_next_branch_by_llm: {e}")
        # フォールバック：従来通り 70/30 で決める
        return (
            "interviewer_llm_generate_slots_2"
            if random.random() < 0.7
            else "interviewer_llm_generate_slots"
        )


# スロット生成の関数を選択するための関数
def select_generate_slots_node(state: State) -> State:
    """
    70%で interviewer_llm_generate_slots_2（ただしスロット候補が空ならスキップして質問へ）、
    30%で interviewer_llm_generate_slots（通常通りその後に質問へ）。
    直前の回答が「わかりません」の場合はinterviewer_llm_generate_slots_2、同様にスロット候補が空ならスキップ。
    """
    new_state = copy.deepcopy(state)
    new_state["slot_generation_count"] = new_state.get("slot_generation_count", 0) + 1

    # 直近のインタビュー対象者の発話を取得
    last_interviewee_utternace = None
    for message in reversed(new_state["dialogue_history"]):
        if message.startswith("インタビュー対象者:"):
            last_interviewee_utternace = message
            break

    pac = list(
        new_state.get("persona_attribute_candidates") or []
    )  # 候補リスト（なければ空）

    def choose_slots_2_or_skip():
        # replay モードの場合、topic_sequence の長さをチェック
        if TOPIC_MODE == "replay":
            topic_sequence = new_state.get("topic_sequence", [])
            replay_index = new_state.get("topic_replay_index", 0)
            if replay_index >= len(topic_sequence):
                # 記録された話題が終わった場合、通常動作に戻る
                if not pac:
                    new_state["branch"] = "skip_to_question"
                else:
                    new_state["branch"] = "interviewer_llm_generate_slots_2"
            else:
                new_state["branch"] = "interviewer_llm_generate_slots_2"
        elif not pac:
            new_state["branch"] = "skip_to_question"
        else:
            new_state["branch"] = "interviewer_llm_generate_slots_2"

    def choose_slots_deep():
        new_state["branch"] = "interviewer_llm_generate_slots"

    # 直前の回答が「わからない」場合
    if last_interviewee_utternace and "わかりません" in last_interviewee_utternace:
        choose_slots_2_or_skip()
        return new_state

    # それ以外の場合：モードに応じて分岐
    if SLOT_SELECTION_MODE == "llm":
        # LLM に決めさせる
        branch = decide_next_branch_by_llm(new_state)

        # persona_attribute_candidates が空なのに slots_2 が選ばれた場合は skip にフォールバック
        if branch == "interviewer_llm_generate_slots_2":
            if TOPIC_MODE == "replay":
                topic_sequence = new_state.get("topic_sequence", [])
                replay_index = new_state.get("topic_replay_index", 0)
                if replay_index >= len(topic_sequence):
                    # 記録された話題が終わった場合、通常動作に戻る
                    if not pac:
                        new_state["branch"] = "skip_to_question"
                    else:
                        new_state["branch"] = branch
                else:
                    new_state["branch"] = branch
            elif not pac:
                new_state["branch"] = "skip_to_question"
            else:
                new_state["branch"] = branch
        else:
            new_state["branch"] = branch
    else:
        # 従来のランダムロジック (デフォルト)
        if random.random() < 0.7:
            choose_slots_2_or_skip()
        else:
            choose_slots_deep()

    return new_state


# インタビュー終了時の処理
def end_interview(state: State) -> State:
    """
    end_interview: インタビューを終了する関数

    Args:
        state(State): 状態情報
    Returns:
        Dict: 更新された状態情報(インタビュー終了)
    """
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

    # record モードの場合、話題順を保存
    if TOPIC_MODE == "record":
        topic_sequence = new_state.get("topic_sequence", [])
        if topic_sequence:
            save_topic_order(topic_sequence, topic_order_path)

    now = datetime.datetime.now(jst)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    node_name = "end_interview"
    this_node_path = os.path.join(
        execution_folder, f"info_{timestamp}_{node_name}.json"
    )

    save_state_to_file(new_state, this_node_path)
    save_state_to_file(new_state, info_path)

    return new_state


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

    dialogue_history = new_state["dialogue_history"]
    max_total_count = new_state["max_total_count"]
    min_total_count = new_state["min_total_count"]
    sc = new_state["speak_count"]
    total_count = sc["total_count"]
    current_slots = new_state["slots"]

    if min_total_count is not None and total_count < min_total_count:
        output = "continue"
        return output

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
        dialogue_history_str=dialogue_history_str,
        current_slots=current_slots,
    )

    human_message = "判定:"

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


def extract_final_output(text: str) -> str:
    marker = "# 最終出力"
    if marker not in text:
        return text.strip()
    return text.split(marker, 1)[1].strip()


# ペルソナ情報の推定を行う関数
def interviewer_llm_estimate_persona(state: State) -> State:
    """
    interviewer_llm_estimate_persona: ペルソナ情報の推定を行う関数

    Args:
        state(State): 状態情報
    Returns:
        Dict: 推定されたペルソナ情報
    """
    time.sleep(WAIT_TIME)
    new_state = copy.deepcopy(state)

    dialogue_history = new_state["dialogue_history"]
    slots = new_state["slots"]
    estimate_persona = new_state["estimate_persona"]

    # ペルソナ情報の推定
    template = prompt_estimate_persona
    prompt = PromptTemplate(
        template=template,
        input_variables=["dialogue_history_str", "current_slots", "estimate_persona"],
    )

    dialogue_history_str = "\n".join(dialogue_history)
    system_message = prompt.format(
        dialogue_history_str=dialogue_history_str,
        current_slots=slots,
        estimate_persona=estimate_persona,
    )

    human_message = "出力:"

    print(
        f"\n\n===============関数interviewer_llm_estimate_persona===============\nSystemMessage=\n{system_message}\nHumanMessage=\n{human_message}\n"
    )

    try:
        response = model.invoke(
            [
                SystemMessage(content=system_message),
                HumanMessage(content=human_message),
            ]
        )
        if response and hasattr(response, "content"):
            raw_output = response.content.strip()
            print(f"estimated_persona: {raw_output}\n")
            estimated_persona = extract_final_output(raw_output)
        else:
            estimated_persona = "ペルソナ情報の推定に失敗しました。"
    except Exception as e:
        print(f"Error occurred while invoking the model: {e}")
        estimated_persona = "ペルソナ情報の推定に失敗しました。"

    new_state["estimate_persona"] = estimated_persona

    now = datetime.datetime.now(jst)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    node_name = "interviewer_llm_estimate_persona"
    this_node_path = os.path.join(
        execution_folder, f"info_{timestamp}_{node_name}.json"
    )

    save_state_to_file(new_state, this_node_path)

    return new_state


# -----状態遷移図の作成-----

# Graph（状態遷移図）の作成
graph_builder = StateGraph(State)

# ノードの追加
# graph_builder.add_node("interviewer_llm_idle_talk", interviewer_llm_idle_talk)
graph_builder.add_node(
    "interviewer_llm_generate_question", interviewer_llm_generate_question
)
graph_builder.add_node("interviewer_llm_fill_slots", interviewer_llm_fill_slots)
graph_builder.add_node(
    "interviewer_llm_estimate_persona", interviewer_llm_estimate_persona
)
graph_builder.add_node("interviewer_llm_generate_slots", interviewer_llm_generate_slots)
graph_builder.add_node(
    "interviewer_llm_generate_slots_2", interviewer_llm_generate_slots_2
)
graph_builder.add_node("select_generate_slots_node", select_generate_slots_node)
# graph_builder.add_node("interviewee_llm_idle_talk", interviewee_llm_idle_talk)
graph_builder.add_node(
    "interviewee_llm_generate_answer", interviewee_llm_generate_answer
)
graph_builder.add_node("end_interview", end_interview)

# エッジの追加
graph_builder.add_edge("interviewer_llm_fill_slots", "interviewer_llm_estimate_persona")
graph_builder.add_conditional_edges(
    "interviewer_llm_estimate_persona",
    finish_interview,
    {
        "end": "end_interview",
        "continue": "select_generate_slots_node",
    },
)
graph_builder.add_conditional_edges(
    "select_generate_slots_node",
    lambda st: st["branch"],
    {
        "interviewer_llm_generate_slots": "interviewer_llm_generate_slots",
        "interviewer_llm_generate_slots_2": "interviewer_llm_generate_slots_2",
        "skip_to_question": "interviewer_llm_generate_question",
    },
)
graph_builder.add_edge(
    "interviewer_llm_generate_slots", "interviewer_llm_generate_question"
)
graph_builder.add_edge(
    "interviewer_llm_generate_slots_2", "interviewer_llm_generate_question"
)

graph_builder.add_edge(
    "interviewer_llm_generate_question", "interviewee_llm_generate_answer"
)
graph_builder.add_edge("interviewee_llm_generate_answer", "interviewer_llm_fill_slots")
# graph_builder.add_edge("interviewer", END)


# Graphの始点を宣言
graph_builder.set_entry_point("interviewer_llm_generate_slots_2")

# Graphの終点を宣言
graph_builder.set_finish_point("end_interview")


def main():
    # Graphのコンパイル
    graph = graph_builder.compile()

    # Graphの実行(引数にはStateの初期値を渡す)
    new_state = graph.invoke(
        {
            "dialogue_history": interview_config["dialogue_history"],
            "speak_count": interview_config["speak_count"],
            "max_total_count": interview_config["max_total_count"],
            "min_total_count": interview_config["min_total_count"],
            "estimate_persona": interview_config["estimate_persona"],
            "persona_attribute_candidates": interview_config[
                "persona_attribute_candidates"
            ],
            "slots": interview_config["slots"],
            "slot_generation_count": interview_config["slot_generation_count"],
            "branch": interview_config["branch"],
            "last_generated_slot": interview_config["last_generated_slot"],
            "last_question_target_slot": interview_config["last_question_target_slot"],
            "topic_sequence": interview_config["topic_sequence"],
            "topic_replay_index": interview_config["topic_replay_index"],
            "current_topic": interview_config["current_topic"],
        },
        config={
            "recursion_limit": 200,
        },
    )

    # Graphの可視化
    try:
        with open(graph_image_path, "wb") as f:
            f.write(graph.get_graph(xray=True).draw_mermaid_png())
    except Exception as e:
        print(f"Graphの可視化に失敗しました: {e}")

    send_line_notify(
        f"インタビューが終了しました。結果は{execution_folder}に保存されました。"
    )

    print(f"インタビューが終了しました。結果は{execution_folder}に保存されました。")


if __name__ == "__main__":
    main()
