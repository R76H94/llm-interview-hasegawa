import pandas as pd

# 1. プロンプトテンプレートを準備
# prompt_estimate_persona-fewshot-base.txt を作成し、few-shotを挿入する場所に「# Few-shot挿入ポイント」という文字列を書く
# 「# Few-shot挿入ポイント」がfew-shotに置換される
# 2. 以下の設定を変更する

input_prompt_path = "data/hashimoto-nakano/prompt_semi_const/proposed_method/all_domain/prompt_estimate_persona-fewshot-base.txt"
input_csv_path = "out/IT-engineer.csv"
output_prompt_path = "data/hashimoto-nakano/prompt_semi_const/proposed_method/all_domain/prompt_estimate_persona-fewshot.txt"

# 発話者の対象: "llm" / "human" / "both"
target_speaker_type = "both"

# 対象とするインタビューファイル
target_persona_files = [
    "IT_engineer-Persona-Sonoda-202510/01.txt",
    "IT_engineer-Persona-Sonoda-202510/02.txt",
    "IT_engineer-Persona-Sonoda-202510/03.txt",
]

# 何ターン目のデータを使用するか（空リストの場合はすべて）
target_turn_numbers = []

# few-shotを挿入するキーワードと挿入位置
insertion_keyword = "# Few-shot挿入ポイント"

# === ステップ1: プロンプト読み込み ===
with open(input_prompt_path, "r", encoding="utf-8-sig") as f:
    base_prompt = f.read()

# === ステップ2: CSV読み込みとフィルタリング ===
df = pd.read_csv(input_csv_path)

# 発話者の条件
if target_speaker_type == "llm":
    df = df[df["source_type"] == "llm"]
elif target_speaker_type == "human":
    df = df[df["source_type"] == "human"]
elif target_speaker_type == "both":
    df = df[df["source_type"].isin(["llm", "human"])]

# インタビューファイルの絞り込み
if target_persona_files:
    df = df[df["persona_file"].isin(target_persona_files)]

# ターン番号の絞り込み
if target_turn_numbers:
    df = df[df["turn_number"].isin(target_turn_numbers)]


# --- ステップ3: few-shot形式に整形 ---
def format_few_shot(row):
    dialogue = row["dialogue_history"].strip()
    slots = row["existing_slots"].strip()
    true_persona_previous_turn = row["true_persona_previous_turn"].strip()
    true_persona = row["true_persona"].strip()

    return (
        "# 対話履歴\n"
        f"{dialogue}\n"
        "# 既存のスロット\n"
        f"{slots}\n"
        "# 既存の推定ペルソナ\n"
        f"{true_persona_previous_turn}\n"
        "# 新しい推定ペルソナ\n"
        f"{true_persona}\n"
    )


# few-shot整形
few_shot_examples = "\n".join(format_few_shot(row) for _, row in df.iterrows())

# === ステップ4: 挿入位置の処理 ===
if insertion_keyword in base_prompt:
    final_prompt = base_prompt.replace(insertion_keyword, few_shot_examples)
else:
    final_prompt = few_shot_examples + "\n\n" + base_prompt

# === ステップ5: 出力 ===
with open(output_prompt_path, "w", encoding="utf-8-sig") as f:
    f.write(final_prompt)

print("✅ 完了: 新しいプロンプトを出力しました →", output_prompt_path)
