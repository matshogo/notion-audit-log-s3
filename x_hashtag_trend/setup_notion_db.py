#!/usr/bin/env python3
"""Notion にトレンド分析用のデータベースを作成するセットアップスクリプト

使い方:
    python -m x_hashtag_trend.setup_notion_db <parent_page_id>

必要な環境変数:
    NOTION_API_TOKEN: Notion Integration Token
"""

import json
import os
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


NOTION_API_VERSION = "2022-06-28"


def create_database(token: str, parent_page_id: str) -> dict:
    """トレンド分析用の Notion データベースを作成する。"""
    body = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": "X ハッシュタグ トレンド分析"}}],
        "properties": {
            "Name": {"title": {}},
            "Hashtag": {"rich_text": {}},
            "Date": {"date": {}},
            "TotalTweets": {"number": {"format": "number"}},
            "TotalLikes": {"number": {"format": "number"}},
            "TotalRetweets": {"number": {"format": "number"}},
            "AvgLikes": {"number": {"format": "number_with_commas"}},
            "TopHashtags": {"rich_text": {}},
            "TopKeywords": {"rich_text": {}},
        },
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_API_VERSION,
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode("utf-8")
    req = Request(
        "https://api.notion.com/v1/databases",
        data=data,
        headers=headers,
        method="POST",
    )

    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"Notion API エラー ({e.code}): {err_body}", file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m x_hashtag_trend.setup_notion_db <parent_page_id>", file=sys.stderr)
        print("", file=sys.stderr)
        print("parent_page_id: データベースを作成する Notion ページの ID", file=sys.stderr)
        print("  ページ URL: https://www.notion.so/<page_id> から取得", file=sys.stderr)
        sys.exit(1)

    token = os.environ.get("NOTION_API_TOKEN")
    if not token:
        print("エラー: 環境変数 NOTION_API_TOKEN が設定されていません。", file=sys.stderr)
        sys.exit(1)

    parent_page_id = sys.argv[1]
    print(f"Notion データベースを作成中...", file=sys.stderr)
    result = create_database(token, parent_page_id)

    db_id = result["id"]
    db_url = result.get("url", "")

    print(f"\nデータベース作成完了!", file=sys.stderr)
    print(f"  URL: {db_url}", file=sys.stderr)
    print(f"  ID:  {db_id}", file=sys.stderr)
    print(f"\n.env に以下を追加してください:", file=sys.stderr)
    print(f"  NOTION_DATABASE_ID={db_id}", file=sys.stderr)


if __name__ == "__main__":
    main()
