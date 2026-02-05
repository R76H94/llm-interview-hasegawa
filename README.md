# interviewアップデート内容（2026/02/05更新）

## 概要

zero-shotとfew-shotで同じ話題順のインタビューを実施するための機能を追加した。

## 主な変更点

### 1. 話題順の記録・再生機能

- `interviewer_llm_generate_slots_2`関数で選択された話題を記録
- 記録された話題順を使って、2回目のインタビューで同じ話題を再現

### 2. 深堀りスロットの扱い

- `interviewer_llm_generate_slots`(深堀り)は各インタビューで独立に実行
- 話題順の記録・再生対象外

### 3. 設定ファイル (config.yaml)

```yaml
interview:
  topic_mode: "record" # "record", "replay", "free"
  topic_order_file: null # replay時に指定
```

## 実行フロー

### 1回目: zero-shot (話題順を記録)

1. **config.yaml の設定**

```yaml
interview:
  topic_mode: "record"
  topic_order_file: null

paths:
  prompts:
    estimate_persona: "zero-shot用プロンプトのパス"
```

2. **実行**

```bash
python -m src.interview_statetransition.human_interview_experiment_proposed_method 2>&1 | tee -a out/log/$(TZ=Asia/Tokyo date +%Y%m%d_%H%M%S)_output.log
```

3. **出力**

- `out/20260205_143022/topic_order.json` - 話題順が記録されたファイル
- `out/20260205_143022/info.json` - 実験結果

### 2回目: few-shot (同じ話題順で実行)

1. **config.yaml の設定**

```yaml
interview:
  topic_mode: "replay"
  topic_order_file: "out/20260205_143022/topic_order.json" # 1回目の話題順ファイル

paths:
  prompts:
    estimate_persona: "zero-shot用プロンプトのパス"
```

2. **実行**

```bash
python -m src.interview_statetransition.human_interview_experiment_proposed_method 2>&1 | tee -a out/log/$(TZ=Asia/Tokyo date +%Y%m%d_%H%M%S)_output.log
```

3. **出力**

- `out/20260205_154500/info.json` - 同じ話題順での実験結果

## topic_order.json の構造

```json
{
  "execution_time": "2026/02/05 14:30:22",
  "model": "gpt-4o",
  "topic_mode": "record",
  "topic_sequence": [
    {
      "step": 1,
      "selected_topic": "趣味・興味",
      "slot_generation_count": 1
    },
    {
      "step": 2,
      "selected_topic": "仕事・キャリア",
      "slot_generation_count": 2
    },
    {
      "step": 3,
      "selected_topic": "家族構成",
      "slot_generation_count": 3
    }
  ]
}
```

## モード詳細

### record モード

- 話題を選択するたびに`topic_sequence`に記録
- インタビュー終了時に`topic_order.json`を保存
- ランダム選択またはLLMによる選択（`slot_selection_mode`に依存）

### replay モード

- `topic_order_file`から話題順を読み込み
- `topic_sequence`の順番通りに話題を使用（**新規生成はしない**）
- **記録された話題が終わった場合**: `persona_attribute_candidates`からランダムに選択する通常動作に戻る

### free モード（既存動作）

- 話題順の記録・再生を行わない
- 従来通りの動作

## 注意事項

1. **深堀りスロット**
   - `interviewer_llm_generate_slots`は各インタビューで独立
   - 話題順の記録・再生対象外

2. **プロンプトの違い**
   - zero-shotとfew-shotの違いは主にプロンプトファイルで制御
   - `estimate_persona`プロンプトなどを適切に変更すること

## トラブルシューティング

### replay時に話題が見つからない

→ `topic_order_file`のパスが正しいか確認

### 話題順ファイルが保存されない

→ `topic_mode`が`"record"`になっているか確認

# extract_persona_to_csv.py - 使い方

## 概要
複数の`info.json`ファイルから`estimate_persona`を抽出し、比較しやすいCSV形式で出力します。
評価作業の際に使用してください

## 使い方

### 基本的な使い方
```bash
python extract_persona_to_csv.py <info.jsonのパス1> <info.jsonのパス2> ... [オプション]
```

### 具体例

#### 例1: 2つのファイルを比較
```bash
python extract_persona_to_csv.py \
    out/20260205_143022/info.json \
    out/20260205_154500/info.json
```

#### 例2: 出力ファイル名を指定
```bash
python extract_persona_to_csv.py \
    out/20260205_143022/info.json \
    out/20260205_154500/info.json \
    -o zero_vs_few_shot.csv
```

#### 例3: 複数の実験結果をまとめて比較
```bash
python extract_persona_to_csv.py \
    out/20260205_143022/info.json \
    out/20260205_154500/info.json \
    out/20260205_160000/info.json \
    out/20260205_170000/info.json \
    -o experiment_results.csv
```

#### 例4: ワイルドカードで一括指定（bash/zsh）
```bash
python extract_persona_to_csv.py out/*/info.json -o all_results.csv
```

## オプション

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `-o`, `--output` | 出力CSVファイルのパス | `persona_comparison.csv` |

## 出力されるCSV形式

### 構造
```csv
,out/20260205_143022/info.json,out/20260205_154500/info.json,out/20260205_160000/info.json
zero-shot/few-shot,,,
人間/LLM,,,
何人目,,,
行1,思い出・エピソード: 済,思い出・エピソード: 済,思い出・エピソード: 未
行2,仕事の達成感: 済,仕事の達成感: 済,仕事の達成感: 済
行3,キャリア・職場: 済,キャリア・職場: 未,キャリア・職場: 済
行4,未来像: 済,未来像: 済,未来像: 済
```

### ヘッダー行の説明

1. **1行目**: ファイルパス（自動入力）
2. **2行目**: `zero-shot/few-shot` - 手動で記入するための空白行
3. **3行目**: `人間/LLM` - 手動で記入するための空白行
4. **4行目**: `何人目` - 手動で記入するための空白行
5. **5行目以降**: `estimate_persona`の各行

# interviewアップデート内容（2025/12/22更新）

## CoTの追加

- CoT（zero-shot CoT、推論過程を出力させる）：/mnt/work/interview/data/hashimoto-nakano/prompt_semi_const/proposed_method/all_domain_tsuchida/prompt_estimate_persona-zeroshot-CoT.txt
- CoT（few-shot CoT、few-shotにもCoTの推論過程を追加）：/mnt/work/interview/data/hashimoto-nakano/prompt_semi_const/proposed_method/all_domain_tsuchida/prompt_estimate_persona_teacher_human_fewshot-CoT.txt

## CoTの追加に伴いペルソナ推定の出力整形を追加
- 追加関数: `extract_final_output(text: str) -> str`
  - 出力に `# 最終出力` というマーカーが含まれる場合、それ以降のみを採用
  - 含まれない場合は全文を使用
- 変更箇所: `interviewer_llm_estimate_persona`
  - 以前: `estimated_persona = response.content.strip()`
  - 変更後: `raw_output` を受け取り、`extract_final_output(raw_output)` を `estimate_persona` として保存
- 目的: プロンプトが途中経過や説明を返しても、最終結果だけを state に残すため

## READMEに実行時設定の追記機能を追加
- 追加関数: `append_final_config_to_readme(readme_path: str, cfg) -> None`
  - `cfg.model_dump()` を `json.dumps(..., ensure_ascii=False, indent=2)` で整形し、
  - README の末尾に以下の形式で追記するようにした：
    - `## 実行時設定（最終確定値）`
    - ` ```json ... ``` `
- 目的: 実験結果フォルダ単体で「実行時の設定が何だったか」を再現できるようにする

# interviewアップデート内容（2025/11/28更新）

## 質問生成に使用したTarget_Slotをスロットフィリングに活用する機能を追加(wikiのSRW-1に対応)

- 概要
  - 質問生成時にLLMが出力する下記JSONフォーマットのうち、 Target_Slotを「スロットフィリング（fill_slots）」時の入力として使用するかどうかを設定ファイルで切り替えられるようにした。

```
generated_question: {
  "Target_Slot": { "個人の基本的情報": null },
  "Question": "〜〜〜"
}
```

- 設定項目

```
interview:
  use_question_slot_in_fill_slots: true  #true or false
```

- 実装概要
  - interviewer_llm_generate_question内でTarget_Slotをstate["last_question_target_slot"] に保存。
  - interviewer_llm_fill_slots内でUSE_QUESTION_SLOT_IN_FILL_SLOTS == True の場合に限り{target_slot} としてプロンプトに渡すよう変更。
  - `"data/hashimoto-nakano/prompt_semi_const/proposed_method/all_domain_tsuchida/prompt_fill_slots.txt"`に変更を加えたプロンプト`"data/hashimoto-nakano/prompt_semi_const/proposed_method/all_domain_tsuchida/prompt_fill_slots_show_question_slot.txt"`を作成した。（変更部分は要確認）

## スロット生成ノードの遷移方法を設定ファイルで変更できるようにした(wikiのSRW-2に対応)

- 新しい設定項目

```
interview:
  slot_selection_mode: "random"   # 70/30 ランダム（従来方式）
  # slot_selection_mode: "llm"    # LLMが次ノードを決める新方式
```

- 変更の要点
  - これまではgenerate_slotsとgenerate_slots_2の選択は固定:
    - 「わかりません」発話 → 70% 側（slots_2）
    - それ以外 → 70% / 30% ランダム
  - これに対し、新たにLLMに次の遷移先を決めさせる関数を追加。

## LLMが次のスロット生成ノードを決める機能の実装(wikiのSRW-2に対応)

- 新規関数decide_next_branch_by_llmを実装
- LLMに
  - interviewer_llm_generate_slots（深堀り）
  - interviewer_llm_generate_slots_2（深堀り不要）
  - skip_to_question（スロット生成自体不要）のいずれかを選ばせるための関数を作成。

- 使用されるプロンプト
  - prompt_fukabori_questions を新設し、インタビュアーが「深堀りの価値があるか」判断するプロセスを LLM に行わせる。

## select_generate_slots_node を改造し、遷移方式を切り替え可能にした(wikiのSRW-2に対応)

- 仕様
  - 直前の回答が「わかりません」なら強制的にslots_2側（従来通り）
  - それ以外の場合はslot_selection_modeによって挙動を選択
    - "random" → 70/30 のランダム（従来方式）
    - "llm" → _decide_next_branch_by_llm による遷移

## 深堀り判定プロンプト（prompt_fukabori_questions）を新規作成(wikiのSRW-2に対応)

- 主な内容
  - 対話履歴を読み、インタビュアーが「深堀りの価値があるか」判断するロジックを文章で説明
  - 深堀りすべき場合と不要な場合の具体例を提示
  - 出力を
    - interviewer_llm_generate_slots
    - interviewer_llm_generate_slots_2
    - skip_to_questionのいずれか1つに限定し、遷移先を決定

---

## 以下は2025/10/15更新アップデート内容

## ディレクトリ構成

- `configs/`
  設定ファイルを格納
  configs/default.yamlは書き換えない（デフォルト設定）
  configs/local.yamlを実験ごとに設定する

- `data/hashimoto-nakano/`
  ペルソナ設定、プロンプトを格納
  - `persona_settings`
    ペルソナ設定を格納
    - `Nurse-Persona-Hasegawa-202510`：看護師データ（論文には載せない）
    - `IT_engineer-Persona-Sonoda-202510`：ITエンジニア
    - `Store_Staff-Persona-Sonoda-202510`：店舗スタッフ
    - `Teacher-Persona-Sonoda-202510`：先生
  - `prompt_semi_const/`
    プロンプトを格納
    - `baseline/all_domain/`
    ベースライン手法
    - `proposed_method/all_domain/`
    提案手法

- `save_data/estimate_persona/`
  IWSDS2025の結果

- `out/`
  実験実行時の出力
  - `log/`
  実行時のログ
  - 日時ごとの出力ディレクトリ
  実験ごとの詳細な出力（info.json, graph.png など）

- `src/interview_statetransition/`
  ソースコード
  - `human_interview_experiment_baseline.py`
  ベースライン
  - `human_interview_experiment_proposed_method.py`
  提案手法

### `configs/local.yaml`で書き換える部分

以下の項目はインタビューを始める前に必ず書き換える

- estimate_persona: 推定ペルソナ
  - baselineの場合：必ずnull
  - proposed methodの場合：1人目は必ずnull。2人目からは前のインタビューの終了時点のestimate_personaの結果を入力（結果の出力先フォルダ内のinfo.jsonに記録されるnew_state>estimate_personaを参照してコピペし、「済」をすべて「未」に書き換える。default.yamlを参照）
    - 例）4人目の開始前に、3人目の結果出力先フォルダ内のinfo.jsonに記録されるnew_state>estimate_personaを参照してコピペ。その後「済」→「未」に書き換える。
    - 例）リフレッシュ方法: 済  \nキャリア・職場: 済  \n悩みや不満点: 済 → リフレッシュ方法: 未  \nキャリア・職場: 未  \n悩みや不満点: 未
- persona_attribute_candidates: ペルソナ属性候補
  - baselineの場合：必ずconfigs/default.yamlのデフォルト設定と同じ
  - proposed methodの場合：1人目は必ずconfigs/default.yamlのデフォルト設定と同じ。2人目からは前のインタビューの終了時点のpersona_attribute_candidatesの結果を入力する。ペルソナ属性候補は徐々に少なくなっていくはず（結果の出力先フォルダ内のinfo.jsonに記録されるnew_state>persona_attribute_candidatesを参照してコピペ）
- slots: スロット（default.yamlファイルを参照）
  - baselineの場合：必ず`slots: {}`
  - proposed methodの場合：1人目は必ず`slots: {}`。2人目からはまず前のインタビューの終了時点のslotsの結果をコピペ。この状態では、各スロットの値が入っている状態なので、値をすべてnullに変更する
- path.persona_settings: インタビュー対象者のペルソナ設定ファイルのパスを設定
- run.out_dir: 結果の出力先（任意）
- interview.max_total_count/min_total_count: 会話ターン数の指定（任意）

### 実行方法

```bash
python -m src.interview_statetransition.human_interview_experiment_proposed_method 2>&1 | tee -a out/log/$(TZ=Asia/Tokyo date +%Y%m%d_%H%M%S)_output.log
```

# 生成物（出力）

実行時に out/<YYYYMMDD_HHMMSS>/ が作られ、以下が保存されます。
- info.json: モデル情報、実行コマンド、ペルソナ設定、インタビュー設定、最新状態（new_state）を含むメタ情報
  - interview_infoには初期設定値が記録されます
  - new_stateにはインタビュー終了時点の情報が記録されます
  - ここを見れば、インタビュー開始時と終了時点の情報がわかります。しかし、インタビューの途中がどうなっているのかは分からないので、インタビュー途中の情報を見たいときはinfo_＜タイムスタンプ＞_＜ノード名＞.jsonもしくはout/log/*.log を参照する
- _README.md: 開始時刻／モデル／ペルソナファイルのパスなどの簡易メモ
- graph.png: 状態遷移グラフの可視化
- info_＜タイムスタンプ＞_＜ノード名＞.json: 各ノード通過時のスナップショット（dialogue_history, speak_count, slots 等）
併せて、ログは起動方法に応じて out/log/*.log に保存されます。

---

以下は2025/10/08以前の情報なので、それ以降は使用しない

## ディレクトリ構成

- `src/`
  ソースコード一式。主なサブディレクトリ・ファイルは以下の通りです。

  - `interview_statetransition/`
    状態遷移を用いたインタビュー対話生成のメイン実装群。
    - `interview_statetransition_semi_constructed_persona_estimate_hikitsugi_pool.py`
      本実験のメインプログラム。半構造化インタビューの状態遷移・ペルソナ推定・スロット管理・対話履歴保存・可視化など一連の流れを制御します。
    - `interview_statetransition_semi_constructed_persona_estimate_hikitsugi.py`
      上記のバリエーション。スロットやペルソナ推定の方法が異なる実装（使わない）。
    - `interview_statetransition_semi_constructed_persona_estimate_kotei.py`
      固定的なスロット・ペルソナ推定を行うバージョン。
    - `before_20250129/`
      過去バージョンの実装群（アブレーションや旧方式の比較用）。

- `data/`
  実験用データ・プロンプト・ペルソナ設定・アンケート等を格納。
  - `hashimoto-nakano/`
    実験用プロンプト・ペルソナ・対話履歴・アンケート等のデータセット。
    - `prompt_semi_const/proposed_method/`
      提案手法で用いる各種プロンプトテンプレート（スロット生成・質問生成・雑談・ペルソナ推定など）。
    - `persona_settings/hasegawa_data/`
      各被験者のペルソナ設定ファイル。
    - `questionnaire/`
      各被験者の自己評価アンケート（JSON形式）。
    - その他、対話履歴や設定ファイル等。
  - `garbage/`, `try_history_prompt/`, `images/`
    補助的なデータや画像等。

- `save_data/`
  実験結果の保存先。
  - `estimate_persona/`, `before_estimate_persona/`
    ペルソナ推定結果や過去の推定結果。

- `out/`
  実験実行時の出力（ログ、結果ファイル、可視化画像等）。
  - `log/`
    実行時のログファイル。
  - 日時ごとの出力ディレクトリ（例: `20250202_103636_nouse/`）
    実験ごとの詳細な出力（info.json, graph.png など）。

- `requirements.lock`, `requirements-dev.lock`, `pyproject.toml`
  Python依存パッケージ管理ファイル。

- `README.md`
  本ファイル。

## 実行方法

1. 必要なPythonパッケージをインストールしてください。
2. `src/interview_statetransition/interview_statetransition_semi_constructed_persona_estimate_hikitsugi_pool.py` を実行することで、半構造化インタビュー実験が開始されます。

```bash
python src/interview_statetransition/interview_statetransition_semi_constructed_persona_estimate_hikitsugi_pool.py
```

## 補足

- 各種プロンプトやペルソナ設定ファイルは `data/hashimoto-nakano/` 以下にまとまっています。
- 実験ごとの出力は `out/` 以下に自動保存されます。
- 詳細な実装やパラメータは各Pythonファイルの先頭コメント・docstringを参照してください。

## メインプログラム（interview_statetransition_semi_constructed_persona_estimate_hikitsugi_pool.py）

このプログラムは、半構造化インタビューの自動化実験の中心となるPythonスクリプトです。

### どのようなプログラムか（概要）
- LLM（大規模言語モデル）を用いて、インタビュアーとインタビュー対象者の対話を自動生成します。
- 状態遷移グラフ（LangGraph）を用いて、雑談→本題質問→スロット埋め→ペルソナ推定→終了判定…といった一連の対話フローを明示的に制御します。

### プログラムの主な流れ
1. **各種設定・プロンプト・初期状態の読み込み**
   - モデル名やプロンプトファイル、ペルソナ設定、アンケートデータなどを読み込みます。
2. **状態遷移グラフ（StateGraph）の構築**
   - 雑談ノード、質問生成ノード、スロット埋めノード、ペルソナ推定ノード、終了判定ノードなどを追加。
   - 条件分岐（例：キャリア話題の有無、ターン数、スロット充足度など）で遷移先を制御します。
3. **グラフの実行**
   - 初期状態を与えてグラフを実行し、対話を自動生成。
   - 各ノードで状態（対話履歴・スロット・ペルソナ等）を逐次更新します。
4. **結果の保存・可視化・通知**
   - 実験ごとの出力ディレクトリにinfo.jsonや状態遷移グラフ画像を保存。

### 主な特徴
- **LLMによる対話生成**（OpenAI GPT-4o など）
- **状態遷移グラフによる対話制御**（LangGraph）
- **スロットフィリング・ペルソナ推定**
- **プロンプトテンプレートの柔軟な切り替え**
- **実験ログ・出力の自動保存**
