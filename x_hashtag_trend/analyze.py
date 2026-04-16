"""取得したツイートデータのトレンド分析を行う"""

import json
import re
from collections import Counter
from datetime import datetime


def analyze_tweets(tweets: list[dict]) -> dict:
    """ツイートリストからトレンド分析結果を生成する。

    Returns:
        分析結果の dict:
        - summary: 概要統計
        - time_distribution: 時間帯別ツイート数
        - top_tweets: エンゲージメント上位ツイート
        - co_hashtags: 共起ハッシュタグ
        - top_authors: 投稿数上位アカウント
        - keyword_freq: 頻出キーワード
    """
    if not tweets:
        return {"summary": {"total_tweets": 0}, "error": "ツイートが見つかりませんでした"}

    # --- 概要統計 ---
    metrics_keys = ["retweet_count", "reply_count", "like_count", "quote_count",
                    "impression_count", "bookmark_count"]
    total_metrics = {k: 0 for k in metrics_keys}
    for t in tweets:
        pm = t.get("public_metrics", {})
        for k in metrics_keys:
            total_metrics[k] += pm.get(k, 0)

    summary = {
        "total_tweets": len(tweets),
        "total_likes": total_metrics["like_count"],
        "total_retweets": total_metrics["retweet_count"],
        "total_replies": total_metrics["reply_count"],
        "total_impressions": total_metrics["impression_count"],
        "avg_likes": round(total_metrics["like_count"] / len(tweets), 1),
        "avg_retweets": round(total_metrics["retweet_count"] / len(tweets), 1),
    }

    # --- 時間帯別分布 ---
    hour_counter = Counter()
    date_counter = Counter()
    for t in tweets:
        created = t.get("created_at", "")
        if created:
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                hour_counter[dt.hour] += 1
                date_counter[dt.strftime("%Y-%m-%d")] += 1
            except ValueError:
                pass

    time_distribution = {
        "by_hour": dict(sorted(hour_counter.items())),
        "by_date": dict(sorted(date_counter.items())),
    }

    # --- エンゲージメント上位ツイート ---
    def engagement_score(t):
        pm = t.get("public_metrics", {})
        return (pm.get("like_count", 0) * 1
                + pm.get("retweet_count", 0) * 2
                + pm.get("reply_count", 0) * 1.5
                + pm.get("quote_count", 0) * 2)

    sorted_tweets = sorted(tweets, key=engagement_score, reverse=True)
    top_tweets = []
    for t in sorted_tweets[:10]:
        author = t.get("author", {})
        top_tweets.append({
            "text": t.get("text", ""),
            "author_name": author.get("name", ""),
            "author_username": author.get("username", ""),
            "metrics": t.get("public_metrics", {}),
            "created_at": t.get("created_at", ""),
            "engagement_score": engagement_score(t),
        })

    # --- 共起ハッシュタグ ---
    hashtag_counter = Counter()
    for t in tweets:
        tags = re.findall(r"[#＃](\w+)", t.get("text", ""))
        for tag in tags:
            hashtag_counter[tag.lower()] += 1

    co_hashtags = [
        {"tag": tag, "count": count}
        for tag, count in hashtag_counter.most_common(20)
    ]

    # --- 投稿数上位アカウント ---
    author_counter = Counter()
    author_info = {}
    for t in tweets:
        author = t.get("author", {})
        uid = author.get("username", t.get("author_id", "unknown"))
        author_counter[uid] += 1
        if uid not in author_info:
            author_info[uid] = {
                "name": author.get("name", ""),
                "username": uid,
                "followers": author.get("public_metrics", {}).get("followers_count", 0),
            }

    top_authors = [
        {**author_info.get(uid, {}), "tweet_count": count}
        for uid, count in author_counter.most_common(10)
    ]

    # --- 頻出キーワード（簡易） ---
    stop_words = {
        "の", "は", "が", "を", "に", "で", "と", "も", "な", "た", "だ", "です",
        "ます", "する", "ない", "ある", "いる", "れる", "この", "その", "あの",
        "して", "から", "まで", "より", "ため", "こと", "もの", "さん", "ちゃん",
        "https", "http", "co", "RT", "the", "and", "for", "you", "that", "with",
    }
    word_counter = Counter()
    for t in tweets:
        text = t.get("text", "")
        # URL を除去
        text = re.sub(r"https?://\S+", "", text)
        # ハッシュタグ・メンションを除去
        text = re.sub(r"[#＃@]\w+", "", text)
        # 2文字以上のカタカナ・漢字・英単語を抽出
        words = re.findall(r"[\u30A0-\u30FF]{2,}|[\u4E00-\u9FFF]{2,}|[a-zA-Z]{3,}", text)
        for w in words:
            if w.lower() not in stop_words and len(w) >= 2:
                word_counter[w.lower()] += 1

    keyword_freq = [
        {"word": word, "count": count}
        for word, count in word_counter.most_common(30)
    ]

    return {
        "summary": summary,
        "time_distribution": time_distribution,
        "top_tweets": top_tweets,
        "co_hashtags": co_hashtags,
        "top_authors": top_authors,
        "keyword_freq": keyword_freq,
    }


def format_analysis_text(hashtag: str, analysis: dict) -> str:
    """分析結果を人間が読みやすいテキストに変換する。"""
    s = analysis.get("summary", {})
    lines = [
        f"=== #{hashtag} トレンド分析レポート ===",
        "",
        f"総ツイート数: {s.get('total_tweets', 0)}",
        f"総いいね数: {s.get('total_likes', 0)} (平均: {s.get('avg_likes', 0)})",
        f"総リツイート数: {s.get('total_retweets', 0)} (平均: {s.get('avg_retweets', 0)})",
        f"総リプライ数: {s.get('total_replies', 0)}",
        f"総インプレッション数: {s.get('total_impressions', 0)}",
        "",
    ]

    # 日別分布
    by_date = analysis.get("time_distribution", {}).get("by_date", {})
    if by_date:
        lines.append("--- 日別ツイート数 ---")
        for date, count in sorted(by_date.items()):
            bar = "█" * min(count, 50)
            lines.append(f"  {date}: {bar} {count}")
        lines.append("")

    # 時間帯別分布
    by_hour = analysis.get("time_distribution", {}).get("by_hour", {})
    if by_hour:
        lines.append("--- 時間帯別ツイート数 (UTC) ---")
        for hour in range(24):
            count = by_hour.get(hour, 0)
            bar = "█" * min(count, 40)
            lines.append(f"  {hour:02d}時: {bar} {count}")
        lines.append("")

    # 共起ハッシュタグ
    co_tags = analysis.get("co_hashtags", [])
    if co_tags:
        lines.append("--- 共起ハッシュタグ TOP10 ---")
        for item in co_tags[:10]:
            lines.append(f"  #{item['tag']}: {item['count']}回")
        lines.append("")

    # 頻出キーワード
    keywords = analysis.get("keyword_freq", [])
    if keywords:
        lines.append("--- 頻出キーワード TOP15 ---")
        for item in keywords[:15]:
            lines.append(f"  {item['word']}: {item['count']}回")
        lines.append("")

    # トップツイート
    top = analysis.get("top_tweets", [])
    if top:
        lines.append("--- エンゲージメント上位ツイート TOP5 ---")
        for i, t in enumerate(top[:5], 1):
            text_preview = t["text"][:100].replace("\n", " ")
            lines.append(f"  {i}. @{t['author_username']} (score: {t['engagement_score']:.0f})")
            lines.append(f"     {text_preview}...")
            m = t.get("metrics", {})
            lines.append(f"     ♥{m.get('like_count',0)} 🔁{m.get('retweet_count',0)} 💬{m.get('reply_count',0)}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <tweets.json>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        tweets = json.load(f)

    result = analyze_tweets(tweets)
    hashtag = sys.argv[2] if len(sys.argv) > 2 else "unknown"
    print(format_analysis_text(hashtag, result))
