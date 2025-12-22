# test_estimate_persona.py
# python -m src.interview_statetransition.test 2>&1
import os
import time
import copy
import sys

from typing import Dict, List, Optional, TypedDict

# --- LangChain (元コードと同系統) ---
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage

# 実LLMを使う場合だけ必要（コメントアウト解除して使う）
from langchain_openai import ChatOpenAI

# from langchain_google_genai import ChatGoogleGenerativeAI

from .config import load_config

cfg = load_config()

# 推定プロンプトは「元のPROMPT_ESTIMATE_PERSONAの中身」を貼るのがベスト。
# ここではテスト用に簡易テンプレを置いています。
PROMPT_ESTIMATE_PERSONA_PATH = cfg.paths.prompts.estimate_persona


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


prompt_estimate_persona = load_file(PROMPT_ESTIMATE_PERSONA_PATH)


# =========================
# 1) State 型定義（最小）
# =========================
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
    max_total_count: Optional[int]
    min_total_count: Optional[int]
    estimate_persona: Optional[str]
    persona_attribute_candidates: List[str]
    slots: Dict
    slot_generation_count: int
    branch: Optional[str]
    last_generated_slot: List[str]
    last_question_target_slot: Dict[str, Optional[str]]


# =========================
# 2) 依存物の最小実装
# =========================

WAIT_TIME = 0  # 単体テストなので 0 推奨


# 保存処理は単体テストでは不要なので no-op にする（必要ならファイル保存実装に差し替え可能）
def save_state_to_file(state: State, file_path: str):
    pass


# =========================
# 3) モデルの差し替え（モック or 実LLM）
# =========================


class FakeResponse:
    def __init__(self, content: str):
        self.content = content


class FakeModel:
    """LLM呼び出しを模擬して、入力(SystemMessage)から適当に固定返答するモック"""

    def invoke(self, messages):
        # messages = [SystemMessage(...), HumanMessage(...)]
        # ここで messages[0].content を解析しても良い
        return FakeResponse(
            """
# 思考過程
1. **情報の重要度判断**
   対話履歴と既存スロットを確認すると、以下の情報が具体的であり、対象者の人物像を深く理解する上で重要と判断される。
   - 職種: IT系
   - 転職意向: あり（検討中）
   - 価値観: 成長環境、新技術
   これらは対象者のキャリアや職業観に関する情報であり、人物像の中心を形成するため重要と判断する。

2. **候補情報の抽出**
   上記の情報はすべてスロットの値がnullではなく、具体的な内容が含まれているため、「重要な情報」候補として抽出する。

3. **抽象化と統合**
   - 「職種」と「転職意向」は、キャリアに関する情報であるため、「キャリア・職場」に統合する。
   - 「価値観」は、職業観や成長意欲に関する情報であり、独立した属性として保持する。

4. **状態の更新**
   - 「キャリア・職場」については具体的な情報が得られているため「済」とする。
   - 「価値観」についても具体的な情報が得られているため「済」とする。

# 最終出力
キャリア・職場: 済
価値観: 済"""
        )


# デフォルトはモック
# model = FakeModel()

# 実LLMを使いたい場合は上をコメントアウトして、下を使う
# 例: OpenAI
model = ChatOpenAI(model="gpt-4o-2024-11-20", temperature=0)
# 例: Google
# model = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.0)


def extract_final_output(text: str) -> str:
    marker = "# 最終出力"
    if marker not in text:
        return text.strip()
    return text.split(marker, 1)[1].strip()


# =========================
# 4) 切り出した対象関数（ほぼ原形）
# =========================
def interviewer_llm_estimate_persona(state: State) -> State:
    """
    interviewer_llm_estimate_persona: ペルソナ情報の推定を行う関数（単体テスト用に周辺依存を最小化）
    """
    time.sleep(WAIT_TIME)
    new_state = copy.deepcopy(state)

    dialogue_history = new_state["dialogue_history"]
    slots = new_state["slots"]
    estimate_persona = new_state["estimate_persona"]

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
        "\n\n===============関数interviewer_llm_estimate_persona===============\n"
        f"SystemMessage=\n{system_message}\n\nHumanMessage=\n{human_message}\n"
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

    # 単体テストでは保存は無効化。必要なら有効化してOK。
    save_state_to_file(new_state, "dummy.json")
    return new_state


# =========================
# 5) 入出力テスト（サンプルState）
# =========================
def build_sample_state() -> State:
    return {
        "dialogue_history": [
            "インタビュアー: 今日はよろしくお願いします。まず簡単に自己紹介をお願いします。",
            "インタビュー対象者: 都内でIT系の仕事をしています。最近は転職も少し考えています。",
            "インタビュアー: 仕事で大事にしていることは何ですか？",
            "インタビュー対象者: 成長できる環境かどうかですね。新しい技術も触りたいです。",
        ],
        "speak_count": {
            "total_count": 4,
            "interviewer_count": 2,
            "interviewee_count": 2,
            "interviewer_idle_talk_count": 0,
            "interviewee_idle_talk_count": 0,
            "interviewer_generate_question_count": 2,
            "interviewee_generate_answer_count": 2,
        },
        "max_total_count": 20,
        "min_total_count": 5,
        "estimate_persona": None,
        "persona_attribute_candidates": ["居住地", "職業", "家族構成"],
        "slots": {
            "職種": "IT系",
            "転職意向": "あり（検討中）",
            "価値観": "成長環境、新技術",
        },
        "slot_generation_count": 0,
        "branch": None,
        "last_generated_slot": [],
        "last_question_target_slot": {},
    }


if __name__ == "__main__":
    state_in = build_sample_state()
    state_out = interviewer_llm_estimate_persona(state_in)

    print("=== 入力 estimate_persona ===")
    print(state_in["estimate_persona"])
    print("\n=== 出力 estimate_persona ===")
    print(state_out["estimate_persona"])
