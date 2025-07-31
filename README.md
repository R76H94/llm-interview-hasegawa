# interview

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
