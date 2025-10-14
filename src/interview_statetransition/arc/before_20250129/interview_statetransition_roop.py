# python src/interview_statetransition/interview_statetransition_roop.py > out/output_$(date +%Y%m%d_%H%M%S).log 2>&1

# ループを使ってインタビューを行うプログラム

import os
import json
import datetime
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from typing import Dict, TypedDict, List, Annotated
from langgraph.graph import StateGraph, START, END
from icecream import ic

ic.enable()
# ic.disable()

# デバッグ出力のフォーマットを設定
ic.configureOutput(includeContext=True)

# モデルの定義
model = ChatOpenAI(
    model_name="gpt-4o-2024-11-20",
    temperature=0.1,
)


def load_persona(file_path: str) -> dict:
    """
    ペルソナ情報をファイルから読み込む関数

    Args:
        file_path(str): ペルソナ情報のファイルパス
    Returns:
        dict: ペルソナ情報
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"ファイルが見つかりません: {file_path}")

    with open(file_path, "r", encoding="utf-8-sig") as f:
        persona = json.load(f)
    return persona


# ペルソナファイルのパス
persona_file_path = "../../data/interviewee_persona/persona_1.json"

# ペルソナ情報の読み込み
interviewee_persona = load_persona(persona_file_path)

# インタビューの設定
interview_config = {
    "theme": "看護師のキャリア面談",
    "history": [],
    "speak_count": 0,
    "max_turns": 3,  # 最大ターン数, Noneで無制限
    "interviewer": {
        "name": "インタビュアー",
        "role": "インタビュアー",
    },
    "interviewee": interviewee_persona,
}

# ic(interview_config)


# 保存フォルダの作成
def create_output_folder(base_folder="../../out/"):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_path = os.path.join(base_folder, timestamp)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path


# 保存するデータの初期化
execution_folder = create_output_folder()
info_path = os.path.join(execution_folder, "info.json")
graph_image_path = os.path.join(execution_folder, "graph.png")

# 保存される情報
execution_info = {
    "execution_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "command": __file__ if "__file__" in globals() else "<interactive>",
    "model_info": {
        "model_name": model.model_name,
        "temperature": model.temperature,
    },
    "interview_info": {
        "theme": interview_config["theme"],
        "history": interview_config["history"],
        "speak_count": interview_config["speak_count"],
        "max_turns": interview_config["max_turns"],
        "interviewer": interview_config["interviewer"],
        "interviewee": interview_config["interviewee"],
    },
    "new_state": {},
}


class State(TypedDict):
    """
    State：ノード間の遷移の際に保存される情報
    各ノードが参照、更新する

    Attributes:
        theme(str): インタビューテーマ
        history(List[str]): インタビューの履歴
        speak_count(int): 発言回数
    """

    theme: str
    history: List[str]
    speak_count: int


# 情報を保存する関数
def save_state_to_file(state: State, file_path: str):
    """
    現在の状態をファイルに保存する関数

    Args:
        state(State): 状態情報
        file_path(str): 保存先のファイルパス
    """
    ic(state)
    execution_info["new_state"].update(state)

    try:
        with open(file_path, "w", encoding="utf-8-sig") as f:
            json.dump(execution_info, f, indent=4, ensure_ascii=False)
        print(f"状態を保存しました: {file_path}")
    except Exception as e:
        print(f"状態の保存に失敗しました: {e}")


def interviewer_llm_start(state: State):
    """
    interviewer_llm_start: インタビューの開始時に呼ばれる関数
    インタビュアーの最初の発言を生成する

    Args:
        state(State): 状態情報
    Returns:
        Dict: 更新された状態情報(インタビュアーの発言, 発言回数)
    """
    ic(state)
    history = state.get("history", [])
    theme = state.get("theme", "")
    speak_count = state.get("speak_count", 0)

    system_message = f"""あなたは優秀な{interview_config['interviewer']['role']}です。\n今回のインタビューのテーマは「{theme}」で、ユーザーに対して質問をしながらインタビューを行います。"""

    human_message_prefix = f"""始めにインタビュー対象者の職業を確認し、インタビューを開始します。\nインタビューの最初の発言を作成してください。"""

    human_message = human_message_prefix + "\n".join(history) + "\nインタビュアー: "

    print(
        f"\n\n関数interviewer_llm_start\nSystemMessage={system_message}\nHumanMessage={human_message}\n\n"
    )

    try:
        response = model.invoke(
            [
                SystemMessage(content=system_message),
                HumanMessage(content=human_message),
            ]
        )
        if response and hasattr(response, "content"):
            updated_state = {
                "history": history + [f"インタビュアー: {response.content}"],
                "speak_count": speak_count + 1,
            }
        else:
            updated_state = {
                "history": history
                + [
                    "インタビュアー: モデルの呼び出しに失敗しました。再試行してください。"
                ],
                "speak_count": speak_count,
            }

    except Exception as e:
        print(f"Error occurred while invoking the model: {e}")
        updated_state = {
            "history": history
            + ["インタビュアー: モデルの呼び出しに失敗しました。再試行してください。"],
            "speak_count": speak_count,
        }
    ic(updated_state)
    save_state_to_file(updated_state, info_path)

    return updated_state


def interviewer_llm(state: State):
    """
    interviewer_llm: インタビュアーの発言を生成する関数

    Args:
        state(State): 状態情報
    Returns:
        Dict: 更新された状態情報(インタビュアーの発言, 発言回数)
    """
    ic(state)
    history = state.get("history", [])
    theme = state.get("theme", "")
    speak_count = state.get("speak_count", 0)

    system_message = f"""あなたは優秀な{interview_config['interviewer']['role']}です。\n今回のインタビューのテーマは「{theme}」で、ユーザーに対して質問をしながらインタビューを行います。"""

    human_message_prefix = f"""「半構造化インタビュー」を行います。以下の条件に従って、インタビューを行ってください。\n\n# テーマ\nインタビューのテーマ:{theme}\nこのテーマを常に意識しながら質問を組み立ててください。\n# 形式\n半構造化インタビューとして、インタビュー対象者の回答内容によって新たな質問を柔軟に追加してください。\n重要な話題が出たら相手の考えを深掘りすることを重視してください。\n\n以上の条件を踏まえて、インタビューを行ってください。\nこれまでの会話履歴を見て、次の発話を作成してください。\nインタビューを終えても良いと判断した場合は最後に"END"と出力してください。\n\n# 会話履歴\n"""

    # その他の注意点
    # 被験者の話を遮らず、積極的に傾聴してください。
    # 相手が答えに詰まった場合は、次の質問へ柔軟に移ってください。
    # 不要な誘導質問（例：「～だと思いますよね？」）は避け、できるだけ中立的な姿勢を保ってください。

    human_message = human_message_prefix + "\n".join(history) + "\nインタビュアー: "

    print(
        f"\n\n関数interviewer_llm\nSystemMessage={system_message}\nHumanMessage={human_message}\n\n"
    )

    try:
        response = model.invoke(
            [
                SystemMessage(content=system_message),
                HumanMessage(content=human_message),
            ]
        )
        if response and hasattr(response, "content"):
            updated_state = {
                "history": history + [f"インタビュアー: {response.content}"],
                "speak_count": speak_count + 1,
            }
        else:
            updated_state = {
                "history": history
                + [
                    "インタビュアー: モデルの呼び出しに失敗しました。再試行してください。"
                ],
                "speak_count": speak_count,
            }

    except Exception as e:
        print(f"Error occurred while invoking the model: {e}")
        updated_state = {
            "history": history
            + ["インタビュアー: モデルの呼び出しに失敗しました。再試行してください。"],
            "speak_count": speak_count,
        }
    ic(updated_state)
    save_state_to_file(updated_state, info_path)

    return updated_state


def interviewee_llm(state: State):
    """
    interviewee_llm: インタビュー対象者の発言を生成する関数

    Args:
        state(State): 状態情報
    Returns:
        Dict: 更新された状態情報(インタビュー対象者の発言, 発言回数)
    """
    ic(state)
    history = state.get("history", [])
    theme = state.get("theme", "")
    speak_count = state.get("speak_count", 0)

    # ペルソナのpersonality情報をコンマ区切りで取得
    personality_list = interview_config['interviewee']['personality']
    personality_string = '、'.join(personality_list)

    system_message = f"""ペルソナの情報を与えるので、あなたはそのペルソナになりきってください。\n\n# ペルソナ情報\n名前:{interview_config['interviewee']['name']}\n年齢:{interview_config['interviewee']['age']}歳\n出身:{interview_config['interviewee']['birthplace']}\n性格:{personality_string}\n過去のキャリア:{interview_config['interviewee']['career']['past']}\n現在のキャリア:{interview_config['interviewee']['career']['current']}\n未来像:{interview_config['interviewee']['career']['future']}\n考え:{interview_config['interviewee']['thoughts']}\nその他の設定:{interview_config['interviewee']['other_info']}\n\nあなたはインタビューに参加します。\n今回のインタビューのテーマは「{theme}」で、インタビュアーからの質問に答えます。"""

    human_message_prefix = (
        f"""これまでの会話履歴を見て、次の発話を作成してください。\n\n# 会話履歴\n"""
    )

    human_message = human_message_prefix + "\n".join(history) + "\nインタビュイー: "

    print(
        f"\n\n関数interviewee_llm\nSystemMessage={system_message}\nHumanMessage={human_message}\n\n"
    )

    try:
        response = model.invoke(
            [
                SystemMessage(content=system_message),
                HumanMessage(content=human_message),
            ]
        )
        if response and hasattr(response, "content"):
            updated_state = {
                "history": history + [f"インタビュイー: {response.content}"],
                "speak_count": speak_count + 1,
            }
        else:
            updated_state = {
                "history": history
                + [
                    "インタビュイー: モデルの呼び出しに失敗しました。再試行してください。"
                ],
                "speak_count": speak_count,
            }

    except Exception as e:
        print(f"Error occurred while invoking the model: {e}")
        updated_state = {
            "history": history
            + ["インタビュイー: モデルの呼び出しに失敗しました。再試行してください。"],
            "speak_count": speak_count,
        }
    ic(updated_state)
    save_state_to_file(updated_state, info_path)

    return updated_state


def next_speaker(state: State) -> str:
    """
    next_speaker: 次の発言者を決定する関数
    インタビュアーとインタビュイーの発言を交互に行う。
    最大ターン数に達した場合は会話を終了する。

    Args:
        state (State): 現在の状態情報
    Returns:
        str: 次の遷移先のノード名 ("interviewer", "interviewee", "end")
    """
    history = state.get("history", [])  # 会話履歴を取得
    max_turns = interview_config.get("max_turns", None)  # 最大ターン数を取得
    speak_count = state.get("speak_count", 0)  # 現在の発言回数を取得

    # 最大ターン数に達したら会話を終了
    if max_turns is not None and speak_count >= max_turns:
        return "end"

    # 会話が終了する条件
    if history and "END" in history[-1]:
        return "end"

    # 次の発言者を決定
    return "interviewee"  # 次にインタビュイーが話す


# Graph（状態遷移図）の作成
graph_builder = StateGraph(State)

# ノードの追加
graph_builder.add_node("interviewer_start", interviewer_llm_start)
graph_builder.add_node("interviewer", interviewer_llm)
graph_builder.add_node("interviewee", interviewee_llm)

# エッジの追加
# graph_builder.add_edge(START, "interviewer_start")
graph_builder.add_edge("interviewer_start", "interviewee")
graph_builder.add_edge("interviewee", "interviewer")
# graph_builder.add_edge("interviewer", END)

graph_builder.add_conditional_edges(
    "interviewer",
    next_speaker,
    {
        "interviewee": "interviewee",
        "end": END,
    },
)

# Graphの始点を宣言
graph_builder.set_entry_point("interviewer_start")

# Graphの終点を宣言
# graph_builder.add_end_point("関数")

# Graphのコンパイル
graph = graph_builder.compile()


# Graphの実行(引数にはStateの初期値を渡す)
new_state = graph.invoke(
    {
        "theme": interview_config["theme"],
        "history": interview_config["history"],
        "speak_count": interview_config["speak_count"],
    },
    debug=True,
)

# Graphの可視化
try:
    with open(graph_image_path, 'wb') as f:
        f.write(graph.get_graph(xray=True).draw_mermaid_png())
except Exception as e:
    print(f"Graphの可視化に失敗しました: {e}")

print(f"インタビューが終了しました。結果は{execution_folder}に保存されました。")
