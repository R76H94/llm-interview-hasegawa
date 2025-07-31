# シミュレータ実験共有用ファイル

# ファイル構成
simulator  
persona_settings  
questionnaire  
dialogs.html  
README  
task.txt  
test_config_exeperiment.yml  

## Dialbb-tester関係
### simulator 
https://github.com/c4a-ri/dialbb-tester  
を用いてシミュレータ実験を行う際に必要なファイルです  
詳細はリンク先のREADMEを参照してください   
もし, 使い方が分からない場合はC4A研究所の中野さんに連絡する方が良いと思います  
プロンプトには対話履歴，質問票，ペルソナ設定，大まかな指示が含まれるように設定しています  

### test_config_exeperiment.yml
シミュレータ実験の設定ファイルです    
一括で16名分の対話が行われるように設定しています   

### task.txt
シミュレータへの大まかな指示を記したテキストファイルです  

## ペルソナ関係
### persona_settings
各ペルソナの設定を記したテキストファイルが入ったディレクトリです  
16名分あります

### questionnaire
各ペルソナが回答するならこう答えるだろうという質問票が入ったディレクトリです  
16名分あります  

## dialogs.html
各ペルソナの対話履歴が記録されているhtmlファイルです    
<div id="dialog_A_Endo" class="hidden">  
以上のように記述されている場合はAのモデルと遠藤さんが対話した結果です  
モデルA(1~16): ベースライン手法 (スロット生成無し, 初期スロットのみ)  
モデルB(17~32): 提案手法1 (単純なスロット生成)  
モデルC(33~48): 提案手法2 (仮説形成的スロット生成)  

# 不明点があれば
- ペルソナについて：橋本慧海 (e.hashimoto.611@stn.nitech.ac.jp) (名古屋工業大学 M2)  
  - 12/31~1/4以外ならスムーズに連絡が取れると思います
- dialbb-testerについて: 中野さん  