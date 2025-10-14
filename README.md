# interview（2025/10/15更新）

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
  - proposed methodの場合：1人目は必ずconfigs/default.yamlのデフォルト設定と同じ。2人目からは前のインタビューの終了時点のpersona_attribute_candidatesの結果を入力（結果の出力先フォルダ内のinfo.jsonに記録されるnew_state>persona_attribute_candidatesを参照してコピペ）
- slots: スロット
  - baselineの場合：必ずconfigs/default.yamlのデフォルト設定と同じ（現在のキャリア、悩みや不満点）
  - proposed methodの場合：1人目は必ずconfigs/default.yamlのデフォルト設定と同じ（現在のキャリア、悩みや不満点）。2人目からはまず前のインタビューの終了時点のslotsの結果をコピペ。この状態では、各スロットの"value"内に値が入っている状態なので、"value"の値をすべてnullに変更する
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
