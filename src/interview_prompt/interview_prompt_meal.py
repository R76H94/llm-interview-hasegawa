import os
import openai
from openai import OpenAI
import json
import sys
from icecream import ic
import time

ic.enable()
ic.disable()

API_KEY = os.environ.get("OPENAI_API_KEY")
if not API_KEY:
    print("Error: OPENAI_API_KEYがありません")
    sys.exit(1)

client = OpenAI(api_key=API_KEY)

# 使用するモデルの定義
MODEL_NAME = "gpt-4o-2024-08-06"
# OpenAIモデル一覧 https://platform.openai.com/docs/models
# Anthropicモデル一覧 https://docs.anthropic.com/ja/docs/about-claude/models
# "claude-3-5-sonnet-20241022"


# 会話履歴を格納するjsonファイルのパス
HISTORY_FILE = "../../data/interview_statetransition/conversation_history.json"


# 初期のシステムプロンプト
SYSTEM_MESSAGE = {
    "role": "system",
    "content": """あなたは有能なインタビュアーです。
ユーザーは被面接者であり、あなたはユーザーに対して「昨日のごはん（朝食、昼食、夕食）」に関する詳細なインタビューを行います。
あなたは以下のルールに従ってインタビューを進めてください:

1. 役割：
- あなたはインタビュアーとして振る舞い、ユーザーへの質問を中心に行動します。
- 不要な説明やメタ的なコメントは控え、ユーザーに対する質問と、それに対するフォローアップに専念します。

2. テーマ：ユーザーの昨日のごはん
- ユーザーが昨日食べた朝食、昼食、夕食のメニューを尋ねてください。

3. 質問の進め方：
- ユーザーが回答に詰まった場合は、質問を言い換えたり、ヒントとなるサブトピックを提示したりしてサポートしてください。
- 十分に情報を引き出したと判断したら、次の質問へ進みます。

4. インタビューの終了：
- ユーザーの昨日の食事について十分な情報が引き出せたと判断した段階で、インタビューを終了します。
- インタビュー終了時には、最後の挨拶の後、`exit` という一言を出力して対話を終了してください。

5. スタイル：
- ユーザーが話しやすい雰囲気を作りつつ、必要な情報を引き出すことに注力してください。

以上のルールに従い、ユーザーとのインタビューを行ってください。""",
}


def load_history():
    # 会話履歴をJSONからロードする。なければ初期状態
    if not os.path.exists(HISTORY_FILE):
        # 初期状態としてsystemメッセージのみ
        history = [SYSTEM_MESSAGE]
        with open(HISTORY_FILE, 'w', encoding='utf-8-sig') as f:
            json.dump(history, f, ensure_ascii=False, indent=4)
        return history

    if os.path.getsize(HISTORY_FILE) == 0:
        # 空なら初期状態としてsystemメッセージのみ
        history = [SYSTEM_MESSAGE]
        with open(HISTORY_FILE, 'w', encoding='utf-8-sig') as f:
            json.dump(history, f, ensure_ascii=False, indent=4)
        return history

    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8-sig') as f:
            history = json.load(f)
        return history
    except json.JSONDecodeError:
        # jsonが壊れている場合、初期状態としてsystemメッセージのみ
        history = [SYSTEM_MESSAGE]
        with open(HISTORY_FILE, 'w', encoding='utf-8-sig') as f:
            json.dump(history, f, ensure_ascii=False, indent=4)
        return history


def save_history(history):
    # 更新した会話履歴を保存する
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8-sig') as f:
            json.dump(history, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"会話履歴の保存中にエラーが発生しました: {e}")


def llm_chat_completion(messages, model=MODEL_NAME):
    # 指定されたメッセージとパラメータをもとにLLM(API)からの応答を取得する
    ic(messages)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.8,
        )
        ic(response)
        return response.choices[0].message.content
    except Exception as e:
        print(f"LLMからの応答取得中にエラーが発生しました: {e}")
        return "エラーが発生しました。"


def generate_llm_first_question(history):
    # historyから最初の質問を生成する。
    first_question = llm_chat_completion(history)
    # 最初の質問をhistoryに追加
    history.append({"role": "assistant", "content": first_question})
    save_history(history)
    return first_question


def generate_llm_response(history):
    # 現在の履歴をもとにLLMが対話を生成
    llm_reply = llm_chat_completion(history)
    return llm_reply


def main():
    print(
        f"インタビューを行います。\n使用するLLMは{MODEL_NAME}です。\n会話履歴は{HISTORY_FILE}に保存します。\n会話中にexitと入力すると会話が終了します。\n"
    )

    # 履歴をロード
    history = load_history()
    ic(history)
    time.sleep(1)

    # 初回、LLMから最初の質問を取得するためにLLMへ問い合わせ
    # もしまだユーザーへの質問がhistoryにない場合、LLMに最初の質問をさせる
    if len(history) == 1:  # systemメッセージのみの場合
        first_question = generate_llm_first_question(history)
        ic(first_question)
        print("LLM: " + first_question)

    # 対話ループ
    while True:
        # ユーザーからの回答を取得
        user_input = input("あなた: ")
        ic(user_input)

        # ユーザーが終了を指示した場合、プログラムを終了
        if user_input.strip().lower() in ["exit"]:
            print("インタビューを終了します。")
            sys.exit(0)

        # ユーザーメッセージを履歴に追加
        history.append({"role": "user", "content": user_input})
        save_history(history)

        # LLMからの応答を取得
        llm_reply = generate_llm_response(history)
        ic(llm_reply)

        # LLMの応答を履歴に追加
        history.append({"role": "assistant", "content": llm_reply})
        save_history(history)

        # LLMの応答表示
        print("LLM:", llm_reply)


if __name__ == "__main__":
    main()
