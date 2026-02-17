# Notion Audit Log to S3

NotionのWebhookを使ってAudit logをS3に保存し、Athena + QuickSightで可視化するシステム

## アーキテクチャ

```
Notion Webhook → API Gateway → Lambda → S3 → Athena → QuickSight
```

## 機能

- NotionのAudit logをリアルタイムでS3に保存
- Webhook認証によるセキュアな通信
- 元のJSONと平坦化されたJSONの両方を保存
- Athenaで簡単にクエリ可能
- QuickSightで可視化

## クイックスタート

詳細な手順は **[SETUP_GUIDE.md](./SETUP_GUIDE.md)** を参照してください。

## 前提条件

- AWS CLI設定済み
- AWS SAM CLI インストール済み
- Python 3.9以上

## デプロイ手順

### 1. Webhook Secretの生成

```bash
openssl rand -base64 32
```

生成された文字列を安全に保管してください。

### 2. ビルドとデプロイ

```bash
# ビルド
sam build

# デプロイ
sam deploy --guided --parameter-overrides WebhookSecret=<生成したSecret>
```

デプロイ時の設定：
- Stack Name: `notion-audit-log-s3`
- AWS Region: 任意のリージョン（例: `ap-northeast-1`）
- その他: デフォルト値でOK

### 3. Webhook URLの取得

デプロイ完了後、Outputsに表示される `WebhookUrl` をコピーしてください。

## Notionの設定

1. Notion Workspace Settings → Integrations → Custom SIEM Integration
2. 以下を設定：
   - **Webhook URL**: デプロイで取得したURL
   - **Webhook headers**: 
     - Header name: `x-notion-webhook-secret`
     - Header value: 生成したWebhookSecret

## S3保存形式

```
s3://notion-audit-logs-{AccountId}/
  └── audit-logs/
      ├── original/  # 元のJSON（バックアップ用）
      │   └── 2026/02/10/...
      └── flat/      # 平坦化されたJSON（Athena/QuickSight用）
          └── 2026/02/10/...
```

## Athena + QuickSightでの可視化

詳細は [SETUP_GUIDE.md](./SETUP_GUIDE.md) の「3. Athenaのセットアップ」「4. QuickSightのセットアップ」「5. Notionへの埋め込み」を参照してください。

### 簡単な手順

1. Athenaクエリ結果保存用バケットを作成
2. Athenaでデータベースとテーブルを作成
3. QuickSightでデータセットを作成
4. ダッシュボードを作成
5. （オプション）NotionページにQuickSightダッシュボードを埋め込み

## ログの確認

```bash
# S3に保存されたログを確認
aws s3 ls s3://notion-audit-logs-{AccountId}/audit-logs/flat/ --recursive

# Lambda関数のログを確認
aws logs tail /aws/lambda/notion-webhook-handler --follow
```

## セキュリティ

- Webhook Secretによる認証
- S3バケットはプライベート設定
- バージョニング有効化
- 7年間のログ保持（変更可能）

## コスト見積もり

- Lambda: ほぼ無料（無料枠内）
- S3: 月$0.01以下（1日100イベントの場合）
- Athena: 月$1以下
- QuickSight: $9〜$18/月/ユーザー

**合計**: 月$10〜$20程度

## トラブルシューティング

詳細は [SETUP_GUIDE.md](./SETUP_GUIDE.md) の「5. トラブルシューティング」を参照してください。

## クリーンアップ

```bash
# スタック削除
sam delete

# S3バケットを削除
aws s3 rb s3://notion-audit-logs-{AccountId} --force
aws s3 rb s3://aws-athena-query-results-{AccountId}-{Region} --force
```

## ライセンス

MIT License

## 参考リンク

- [Notion API Documentation](https://developers.notion.com/)
- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [Athena JSON SerDe](https://docs.aws.amazon.com/athena/latest/ug/json-serde.html)
- [QuickSight User Guide](https://docs.aws.amazon.com/quicksight/)
