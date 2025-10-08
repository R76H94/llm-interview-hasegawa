# Interview 2025/10/05

## 構成

新たに以下の4つのファイルを追加してください

- human_interview_experiment.py
- config.py
- default.yaml
- local.yaml

interview/
├── src/
│   └── interview_statetransition/
│       ├── human_interview_experiment.py
│       └── config.py
├── configs/
│   ├── default.yaml   # 実験設定用のYAMLファイル(このファイルは触らない)
│   └── local.yaml     # 実験設定用のYAMLファイル(このファイルを編集して設定を変更する)
├── out/
│   └── log/                 # 実行ログ出力先
└── README.md

## YAML設定ファイル

実験パラメータをYAML形式でまとめる方式に変更
local.yamlを編集して設定を変更する
default.yamlは基本的に触らない

## 実行方法

```bash
python -m src.interview_statetransition.human_interview_experiment 2>&1 | tee -a out/log/output_$(date +%Y%m%d_%H%M%S).log
```
画面に出力を表示しながら、out/log/ にも追記保存する

## 出力とログ

実行ごとに run.out_dir（例：out）配下へ日時フォルダが作られる
その中に以下が保存される:
- info.json：実行メタ情報と最新ステート
- graph.png：状態遷移グラフ（Mermaidレンダリング）
- _README.md：簡易実行ノート
- ノードごとのスナップショット：info_YYYYMMDD_HHMMSS_<node>.json
ログは上記 tee コマンドで out/log/output_YYYYMMDD_HHMMSS.log に保存されます。

## API keyの設定

```bash
export OPENAI_API_KEY='sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
```
