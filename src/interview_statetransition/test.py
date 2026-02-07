import sys

# 書き込みモードでファイルを開く
with open("output.log", "w", encoding="utf-8") as f:
    sys.stdout = f  # 標準出力をファイルに切り替え

    print("この内容はファイルに書き込まれます。")
    print("ターミナルには表示されません。")

# 処理が終われば sys.stdout を元に戻す（必要に応じて）
sys.stdout = sys.__stdout__
