#!/usr/bin/env python3
"""X ハッシュタグ トレンド分析 CLI

使い方:
    python -m x_hashtag_trend.main <hashtag> [--max-tweets N] [--no-notion] [--output FILE]

必要な環境変数:
    X_BEARER_TOKEN      : X API Bearer Token
    NOTION_API_TOKEN    : Notion Integration Token (--no-notion 時は不要)
    NOTION_DATABASE_ID  : Notion データベース ID (--no-notion 時は不要)
"""

import argparse
import json
import sys
from datetime import datetime, timezone

from .analyze import analyze_tweets, format_analysis_text
from .fetch_tweets import fetch_all_tweets, save_tweets_json
from .notion_store import store_analysis


def main():
    parser = argparse.ArgumentParser(
        description="X (Twitter) ハッシュタグのトレンド分析を行い、Notion DB に保存する"
    )
    parser.add_argument("hashtag", help="分析するハッシュタグ (例: AI, Python)")
    parser.add_argument(
        "--max-tweets", type=int, default=300,
        help="取得する最大ツイート数 (デフォルト: 300)",
    )
    parser.add_argument(
        "--no-notion", action="store_true",
        help="Notion への保存をスキップ（分析結果のみ出力）",
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="分析結果 JSON の出力先ファイルパス",
    )
    parser.add_argument(
        "--save-tweets", action="store_true",
        help="取得した生ツイートデータも JSON で保存する",
    )

    args = parser.parse_args()
    hashtag = args.hashtag.lstrip("#")

    # 1. ツイート取得
    print(f"[1/3] #{hashtag} のツイートを取得中...", file=sys.stderr)
    tweets = fetch_all_tweets(hashtag, max_total=args.max_tweets)

    if not tweets:
        print(f"エラー: #{hashtag} のツイートが見つかりませんでした。", file=sys.stderr)
        sys.exit(1)

    # 生データ保存（オプション）
    if args.save_tweets:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        save_tweets_json(tweets, f"data/{hashtag}_{timestamp}.json")

    # 2. トレンド分析
    print(f"[2/3] トレンド分析中...", file=sys.stderr)
    analysis = analyze_tweets(tweets)
    report_text = format_analysis_text(hashtag, analysis)

    # 分析結果 JSON 出力
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2, default=str)
        print(f"分析結果 JSON: {args.output}", file=sys.stderr)

    # 3. Notion 保存
    if not args.no_notion:
        print(f"[3/3] Notion DB に保存中...", file=sys.stderr)
        page_url = store_analysis(hashtag, analysis, report_text)
        print(f"\nNotion ページ: {page_url}", file=sys.stderr)
    else:
        print(f"[3/3] Notion 保存スキップ", file=sys.stderr)

    # レポートを stdout に出力（Claude が読み取る用）
    print(report_text)

    # JSON サマリーも出力
    print("\n---JSON_SUMMARY_START---")
    print(json.dumps(analysis.get("summary", {}), ensure_ascii=False))
    print("---JSON_SUMMARY_END---")


if __name__ == "__main__":
    main()
