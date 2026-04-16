"""Notion DB にトレンド分析結果を保存する"""

import json
import os
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen


NOTION_API_VERSION = "2022-06-28"


def get_notion_config() -> tuple[str, str]:
    """Notion API トークンとデータベース ID を環境変数から取得する。"""
    token = os.environ.get("NOTION_API_TOKEN")
    db_id = os.environ.get("NOTION_DATABASE_ID")

    if not token:
        print("エラー: 環境変数 NOTION_API_TOKEN が設定されていません。", file=sys.stderr)
        print("Notion Integration を作成してトークンを取得してください:", file=sys.stderr)
        print("  https://www.notion.so/my-integrations", file=sys.stderr)
        sys.exit(1)
    if not db_id:
        print("エラー: 環境変数 NOTION_DATABASE_ID が設定されていません。", file=sys.stderr)
        sys.exit(1)

    return token, db_id


def _notion_request(method: str, url: str, token: str, body: dict | None = None) -> dict:
    """Notion API へリクエストを送信する。"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_API_VERSION,
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode("utf-8") if body else None
    req = Request(url, data=data, headers=headers, method=method)

    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"Notion API エラー ({e.code}): {err_body}", file=sys.stderr)
        raise


def ensure_database_schema(token: str, db_id: str) -> None:
    """データベースに必要なプロパティが存在するか確認する（情報表示のみ）。"""
    url = f"https://api.notion.com/v1/databases/{db_id}"
    try:
        db = _notion_request("GET", url, token)
        props = db.get("properties", {})
        print(f"Notion DB: {db.get('title', [{}])[0].get('plain_text', 'Untitled')}", file=sys.stderr)
        print(f"既存プロパティ: {', '.join(props.keys())}", file=sys.stderr)
    except Exception as e:
        print(f"DB スキーマ確認失敗: {e}", file=sys.stderr)


def _truncate(text: str, max_len: int = 2000) -> str:
    """Notion API の制限に合わせて文字列を切り詰める。"""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _build_rich_text_blocks(text: str) -> list[dict]:
    """長いテキストを Notion のリッチテキストブロック群に分割する。
    Notion API は 1 リッチテキスト要素あたり 2000 文字が上限。
    """
    chunks = []
    for i in range(0, len(text), 2000):
        chunks.append({
            "type": "text",
            "text": {"content": text[i:i + 2000]},
        })
    return chunks


def store_analysis(hashtag: str, analysis: dict, report_text: str) -> str:
    """分析結果を Notion DB のページとして作成する。

    Notion DB に以下のプロパティが必要:
        - Name (title): ページタイトル
        - Hashtag (rich_text): ハッシュタグ名
        - Date (date): 分析日時
        - TotalTweets (number): 総ツイート数
        - TotalLikes (number): 総いいね数
        - TotalRetweets (number): 総リツイート数
        - AvgLikes (number): 平均いいね数
        - TopHashtags (rich_text): 共起ハッシュタグ
        - TopKeywords (rich_text): 頻出キーワード

    Returns:
        作成されたページの URL
    """
    token, db_id = get_notion_config()
    now = datetime.now(timezone.utc).isoformat()
    summary = analysis.get("summary", {})

    co_tags = ", ".join(
        f"#{item['tag']}({item['count']})" for item in analysis.get("co_hashtags", [])[:10]
    )
    keywords = ", ".join(
        f"{item['word']}({item['count']})" for item in analysis.get("keyword_freq", [])[:15]
    )

    properties = {
        "Name": {
            "title": [{"text": {"content": f"#{hashtag} トレンド分析 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"}}],
        },
        "Hashtag": {
            "rich_text": [{"text": {"content": f"#{hashtag}"}}],
        },
        "Date": {
            "date": {"start": now},
        },
        "TotalTweets": {
            "number": summary.get("total_tweets", 0),
        },
        "TotalLikes": {
            "number": summary.get("total_likes", 0),
        },
        "TotalRetweets": {
            "number": summary.get("total_retweets", 0),
        },
        "AvgLikes": {
            "number": summary.get("avg_likes", 0),
        },
        "TopHashtags": {
            "rich_text": [{"text": {"content": _truncate(co_tags)}}],
        },
        "TopKeywords": {
            "rich_text": [{"text": {"content": _truncate(keywords)}}],
        },
    }

    # ページ本文にレポート全文を記載
    report_blocks = []
    # ヘッダー
    report_blocks.append({
        "object": "block",
        "type": "heading_2",
        "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": f"#{hashtag} トレンド分析レポート"}}],
        },
    })
    # レポート本文（コードブロックとして貼り付け）
    report_blocks.append({
        "object": "block",
        "type": "code",
        "code": {
            "rich_text": _build_rich_text_blocks(report_text),
            "language": "plain text",
        },
    })

    # トップツイートの詳細
    top_tweets = analysis.get("top_tweets", [])
    if top_tweets:
        report_blocks.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"type": "text", "text": {"content": "エンゲージメント上位ツイート"}}],
            },
        })
        for i, t in enumerate(top_tweets[:5], 1):
            tweet_text = _truncate(
                f"{i}. @{t['author_username']}: {t['text'][:200]}\n"
                f"   ♥{t['metrics'].get('like_count',0)} 🔁{t['metrics'].get('retweet_count',0)}"
            )
            report_blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": tweet_text}}],
                },
            })

    body = {
        "parent": {"database_id": db_id},
        "properties": properties,
        "children": report_blocks,
    }

    result = _notion_request("POST", "https://api.notion.com/v1/pages", token, body)
    page_url = result.get("url", "")
    print(f"Notion ページ作成完了: {page_url}", file=sys.stderr)
    return page_url
