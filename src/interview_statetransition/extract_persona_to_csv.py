#!/usr/bin/env python3
"""
info.jsonファイルからestimate_personaを抽出してCSVを作成するスクリプト

使用例:
    python extract_persona_to_csv.py out/20260205_143022/info.json out/20260205_154500/info.json -o results.csv
"""

import json
import csv
import sys
import argparse
from pathlib import Path
from typing import List, Dict


def load_estimate_persona(info_json_path: str) -> str:
    """
    info.jsonからestimate_personaを抽出する
    
    Args:
        info_json_path(str): info.jsonのパス
    Returns:
        str: estimate_persona文字列
    """
    try:
        with open(info_json_path, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
            return data.get('new_state', {}).get('estimate_persona', '')
    except Exception as e:
        print(f"エラー: {info_json_path} の読み込みに失敗しました: {e}", file=sys.stderr)
        return ''


def parse_persona_lines(estimate_persona: str) -> List[str]:
    """
    estimate_personaを行ごとに分割する
    
    Args:
        estimate_persona(str): estimate_persona文字列
    Returns:
        List[str]: 行ごとのリスト
    """
    if not estimate_persona:
        return []
    
    # 改行で分割し、空行と空白のみの行を除外
    lines = [line.strip() for line in estimate_persona.split('\n') if line.strip()]
    return lines


def create_csv(info_json_paths: List[str], output_path: str):
    """
    複数のinfo.jsonからestimate_personaを抽出してCSVを作成
    
    Args:
        info_json_paths(List[str]): info.jsonのパスリスト
        output_path(str): 出力CSVのパス
    """
    # 各ファイルのestimate_personaを読み込み
    all_personas: List[Dict[str, any]] = []
    max_lines = 0
    
    for path in info_json_paths:
        estimate_persona = load_estimate_persona(path)
        lines = parse_persona_lines(estimate_persona)
        all_personas.append({
            'path': path,
            'lines': lines
        })
        max_lines = max(max_lines, len(lines))
    
    # CSVを作成
    try:
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            
            # 1行目: ファイルパス
            header_row_1 = [''] + [p['path'] for p in all_personas]
            writer.writerow(header_row_1)
            
            # 2行目: zero-shot/few-shotのインデックス（空白で、ユーザが後で記入）
            header_row_2 = ['zero-shot/few-shot'] + [''] * len(all_personas)
            writer.writerow(header_row_2)
            
            # 3行目: 人間/LLMのインデックス（空白で、ユーザが後で記入）
            header_row_3 = ['人間/LLM'] + [''] * len(all_personas)
            writer.writerow(header_row_3)
            
            # 4行目: 何人目かのインデックス（空白で、ユーザが後で記入）
            header_row_4 = ['何人目'] + [''] * len(all_personas)
            writer.writerow(header_row_4)
            
            # データ行: estimate_personaの各行
            for i in range(max_lines):
                row = [f'行{i+1}']
                for persona_data in all_personas:
                    if i < len(persona_data['lines']):
                        row.append(persona_data['lines'][i])
                    else:
                        row.append('')
                writer.writerow(row)
        
        print(f"✓ CSVファイルを作成しました: {output_path}")
        print(f"✓ ファイル数: {len(all_personas)}")
        print(f"✓ 最大行数: {max_lines}")
        
    except Exception as e:
        print(f"エラー: CSVの作成に失敗しました: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='info.jsonファイルからestimate_personaを抽出してCSVを作成',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 2つのファイルを指定
  python extract_persona_to_csv.py out/20260205_143022/info.json out/20260205_154500/info.json

  # 出力ファイル名を指定
  python extract_persona_to_csv.py file1.json file2.json -o results.csv

  # ワイルドカードで複数ファイルを指定（シェルが展開）
  python extract_persona_to_csv.py out/*/info.json -o all_results.csv
        """
    )
    
    parser.add_argument(
        'info_json_paths',
        nargs='+',
        help='info.jsonファイルのパス（複数指定可能）'
    )
    
    parser.add_argument(
        '-o', '--output',
        default='persona_comparison.csv',
        help='出力CSVファイルのパス（デフォルト: persona_comparison.csv）'
    )
    
    args = parser.parse_args()
    
    # ファイルの存在確認
    for path in args.info_json_paths:
        if not Path(path).exists():
            print(f"エラー: ファイルが存在しません: {path}", file=sys.stderr)
            sys.exit(1)
    
    # CSV作成
    create_csv(args.info_json_paths, args.output)


if __name__ == '__main__':
    main()
