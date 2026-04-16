"""X (Twitter) API v2 を使ってハッシュタグのツイートを取得する"""

import json
import os
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


def get_bearer_token() -> str:
    token = os.environ.get("X_BEARER_TOKEN")
    if not token:
        print("エラー: 環境変数 X_BEARER_TOKEN が設定されていません。", file=sys.stderr)
        print("X Developer Portal で Bearer Token を取得してください:", file=sys.stderr)
        print("  https://developer.x.com/en/portal/dashboard", file=sys.stderr)
        sys.exit(1)
    return token


def fetch_recent_tweets(
    hashtag: str,
    max_results: int = 100,
    next_token: str | None = None,
) -> dict:
    """X API v2 の Recent Search で直近7日間のツイートを取得する。

    Args:
        hashtag: 検索するハッシュタグ（# 付きでも無しでも可）
        max_results: 1リクエストあたりの取得件数 (10-100)
        next_token: ページネーション用トークン

    Returns:
        API レスポンスの dict
    """
    tag = hashtag.lstrip("#")
    query = f"#{tag} -is:retweet lang:ja"

    params = {
        "query": query,
        "max_results": min(max(max_results, 10), 100),
        "tweet.fields": "created_at,public_metrics,author_id,lang",
        "expansions": "author_id",
        "user.fields": "name,username,public_metrics",
    }
    if next_token:
        params["next_token"] = next_token

    url = f"https://api.x.com/2/tweets/search/recent?{urlencode(params, quote_via=quote)}"
    req = Request(url, headers={
        "Authorization": f"Bearer {get_bearer_token()}",
        "User-Agent": "x-hashtag-trend-analyzer/1.0",
    })

    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"X API エラー ({e.code}): {body}", file=sys.stderr)
        sys.exit(1)


def fetch_all_tweets(hashtag: str, max_total: int = 500) -> list[dict]:
    """ページネーションで最大 max_total 件のツイートを取得する。

    Returns:
        ツイートの dict リスト。各要素に author 情報をマージ済み。
    """
    all_tweets = []
    users_map = {}
    next_token = None

    while len(all_tweets) < max_total:
        batch_size = min(100, max_total - len(all_tweets))
        data = fetch_recent_tweets(hashtag, max_results=batch_size, next_token=next_token)

        if "includes" in data and "users" in data["includes"]:
            for u in data["includes"]["users"]:
                users_map[u["id"]] = u

        if "data" not in data:
            break

        for tweet in data["data"]:
            tweet["author"] = users_map.get(tweet.get("author_id"), {})
            all_tweets.append(tweet)

        meta = data.get("meta", {})
        next_token = meta.get("next_token")
        if not next_token:
            break

    print(f"取得完了: #{hashtag.lstrip('#')} → {len(all_tweets)} 件", file=sys.stderr)
    return all_tweets


def save_tweets_json(tweets: list[dict], output_path: str) -> str:
    """取得したツイートを JSON ファイルに保存する。"""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(tweets, f, ensure_ascii=False, indent=2, default=str)
    print(f"保存: {output_path}", file=sys.stderr)
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <hashtag> [max_total]", file=sys.stderr)
        sys.exit(1)

    tag = sys.argv[1]
    total = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    tweets = fetch_all_tweets(tag, max_total=total)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = f"data/{tag.lstrip('#')}_{timestamp}.json"
    save_tweets_json(tweets, out)
    print(json.dumps({"count": len(tweets), "file": out}))
