X (Twitter) のハッシュタグ「$ARGUMENTS」のトレンド分析を実行します。

## 手順

1. まず以下のコマンドを実行して、X API からツイートを取得し、トレンド分析を行い、Notion DB に保存してください:

```
python -m x_hashtag_trend.main $ARGUMENTS --save-tweets
```

2. コマンドの出力（トレンド分析レポート）を読み取って、以下の観点で日本語の分析コメントを追加してください:

- **全体的なトレンドの傾向**: ツイート数、エンゲージメントから読み取れる盛り上がり具合
- **話題の中心**: 共起ハッシュタグや頻出キーワードから、何が話題になっているか
- **注目すべきツイート**: 上位ツイートの内容から、特に影響力のある意見や情報
- **時間的なパターン**: 日別・時間帯別の分布から読み取れる投稿パターン
- **今後の予測・示唆**: このトレンドが今後どう展開しそうか

3. 分析が完了したら、結果のサマリーをユーザーに報告してください。

## エラー時

- `X_BEARER_TOKEN` が未設定の場合: X Developer Portal でのトークン取得方法を案内
- `NOTION_API_TOKEN` / `NOTION_DATABASE_ID` が未設定の場合: Notion 保存をスキップして `--no-notion` フラグで再実行
- API レート制限エラーの場合: 15分後に再試行するよう案内

## 使用例

```
/analyze-hashtag AI
/analyze-hashtag Python --max-tweets 500
/analyze-hashtag 生成AI --no-notion
```
