# Notion Audit Log to S3

[日本語](#日本語) | [English](#english)

---

## 日本語

NotionのWebhookを使ってAudit LogをS3に保存し、Notionデータベースで可視化するシステムです。
ページ公開時のメール/Slack通知機能も備えています。

### アーキテクチャ

```
Notion Webhook → API Gateway → Lambda (handler) → S3
                                  ├→ Notionデータベースへリアルタイム書き込み
                                  ├→ ページ公開通知（Email / Slack）
                                  └→ インポートLambda即時実行（ページ公開時）

EventBridge (6時間ごと) → Lambda (importer) → S3読み取り → Notionデータベースへ一括インポート
```

### 機能

- Audit LogをリアルタイムでS3に保存（元JSON + 平坦化JSON）
- Webhook Secretによるセキュアな認証
- Notionデータベースへの自動書き込み（ダッシュボード用）
- ページ公開イベントのメールまたはSlack通知
- S3→Notionデータベースへの一括インポート（定期実行 / 手動実行）
- 重複排除（イベントID単位）
- 取り込みログレベル切り替え（全イベント / ページ公開のみ）
- Athenaによるクエリ分析

### デプロイパラメータ

| パラメータ | 説明 | デフォルト | 必須 |
|---|---|---|---|
| `WebhookSecret` | Webhook認証用シークレット | （空） | 推奨 |
| `NotificationType` | 通知先（`none` / `email` / `slack`） | `none` | - |
| `NotificationEmail` | メール通知先アドレス | （空） | email時 |
| `SlackWebhookUrl` | Slack Incoming Webhook URL | （空） | slack時 |
| `NotionApiKey` | Notion Internal Integration Token | （空） | Notion連携時 |
| `NotionDatabaseId` | NotionデータベースID | （空） | Notion連携時 |
| `ImportLogLevel` | 取り込み対象（`all` / `page_publish_only`） | `all` | - |

### クイックスタート

```bash
# Webhook Secretの生成
openssl rand -base64 32

# ビルド
sam build

# デプロイ（対話形式）
sam deploy --guided
```

または `deploy.sh` を使用：

```bash
./deploy.sh
```

詳細な手順は [SETUP_GUIDE.md](./SETUP_GUIDE.md) を参照してください。

### S3保存形式

```
s3://notion-audit-logs-{AccountId}/
  └── audit-logs/
      ├── original/    # 元のJSON（バックアップ用）
      │   └── YYYY/MM/DD/...
      └── flat/        # 平坦化JSON（Athena / Notionインポート用）
          └── YYYY/MM/DD/...
```

### Notionデータベースのプロパティ

Notion側で以下のプロパティを持つデータベースを作成してください：

| プロパティ名 | 型 |
|---|---|
| イベントID | タイトル |
| イベントタイプ | セレクト |
| ユーザー | メール |
| ワークスペース | テキスト |
| プラットフォーム | セレクト |
| IPアドレス | テキスト |
| 日時 | 日付 |

### S3→Notionインポート（手動実行）

```bash
# 全件インポート
aws lambda invoke --function-name notion-s3-to-notion-importer \
  --payload '{}' --cli-binary-format raw-in-base64-out output.json

# 件数制限付き
aws lambda invoke --function-name notion-s3-to-notion-importer \
  --payload '{"limit": 10}' --cli-binary-format raw-in-base64-out output.json

# 特定月のみ
aws lambda invoke --function-name notion-s3-to-notion-importer \
  --payload '{"prefix": "audit-logs/flat/2026/03/"}' --cli-binary-format raw-in-base64-out output.json
```

### ログの確認

```bash
# S3に保存されたログを確認
aws s3 ls s3://notion-audit-logs-{AccountId}/audit-logs/flat/ --recursive

# Webhook Lambda のログ
aws logs tail /aws/lambda/notion-webhook-handler --follow

# インポートLambda のログ
aws logs tail /aws/lambda/notion-s3-to-notion-importer --follow
```

### セキュリティ

- Webhook Secretによる認証
- S3バケットはプライベート設定（パブリックアクセス全ブロック）
- バージョニング有効化
- 7年間のログ保持（変更可能）
- Notion API Key / Slack Webhook URL は NoEcho でマスク

### コスト見積もり

- Lambda: ほぼ無料（無料枠内）
- S3: 月$0.01以下（1日100イベントの場合）
- Athena: 月$1以下
- SNS（メール通知）: ほぼ無料

合計: 月$1〜$2程度（Notion連携のみの場合）

### クリーンアップ

```bash
sam delete
aws s3 rb s3://notion-audit-logs-{AccountId} --force
```

### ライセンス

MIT License

### 参考リンク

- [Notion API Documentation](https://developers.notion.com/)
- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [Athena JSON SerDe](https://docs.aws.amazon.com/athena/latest/ug/json-serde.html)

---

## English

A system that saves Notion Audit Logs to S3 via Webhook and visualizes them in a Notion database.
Includes email/Slack notification for page publish events.

### Architecture

```
Notion Webhook → API Gateway → Lambda (handler) → S3
                                  ├→ Real-time write to Notion database
                                  ├→ Page publish notification (Email / Slack)
                                  └→ Trigger importer Lambda immediately (on page publish)

EventBridge (every 6 hours) → Lambda (importer) → Read S3 → Bulk import to Notion database
```

### Features

- Real-time Audit Log storage to S3 (original JSON + flattened JSON)
- Secure authentication via Webhook Secret
- Automatic write to Notion database (for dashboards)
- Email or Slack notification on page publish events
- Bulk import from S3 to Notion database (scheduled / manual)
- Deduplication (by event ID)
- Import log level switching (all events / page publish only)
- Query analysis via Athena

### Deploy Parameters

| Parameter | Description | Default | Required |
|---|---|---|---|
| `WebhookSecret` | Webhook authentication secret | (empty) | Recommended |
| `NotificationType` | Notification target (`none` / `email` / `slack`) | `none` | - |
| `NotificationEmail` | Email address for notifications | (empty) | When email |
| `SlackWebhookUrl` | Slack Incoming Webhook URL | (empty) | When slack |
| `NotionApiKey` | Notion Internal Integration Token | (empty) | For Notion integration |
| `NotionDatabaseId` | Notion database ID | (empty) | For Notion integration |
| `ImportLogLevel` | Import target (`all` / `page_publish_only`) | `all` | - |

### Quick Start

```bash
# Generate Webhook Secret
openssl rand -base64 32

# Build
sam build

# Deploy (interactive)
sam deploy --guided
```

Or use the deploy script:

```bash
./deploy.sh
```

See [SETUP_GUIDE.md](./SETUP_GUIDE.md) for detailed instructions.

### S3 Storage Format

```
s3://notion-audit-logs-{AccountId}/
  └── audit-logs/
      ├── original/    # Original JSON (backup)
      │   └── YYYY/MM/DD/...
      └── flat/        # Flattened JSON (for Athena / Notion import)
          └── YYYY/MM/DD/...
```

### Notion Database Properties

Create a Notion database with the following properties:

| Property Name | Type |
|---|---|
| イベントID | Title |
| イベントタイプ | Select |
| ユーザー | Email |
| ワークスペース | Text |
| プラットフォーム | Select |
| IPアドレス | Text |
| 日時 | Date |

### S3 → Notion Import (Manual Execution)

```bash
# Import all records
aws lambda invoke --function-name notion-s3-to-notion-importer \
  --payload '{}' --cli-binary-format raw-in-base64-out output.json

# With limit
aws lambda invoke --function-name notion-s3-to-notion-importer \
  --payload '{"limit": 10}' --cli-binary-format raw-in-base64-out output.json

# Specific month only
aws lambda invoke --function-name notion-s3-to-notion-importer \
  --payload '{"prefix": "audit-logs/flat/2026/03/"}' --cli-binary-format raw-in-base64-out output.json
```

### Check Logs

```bash
# Check logs saved to S3
aws s3 ls s3://notion-audit-logs-{AccountId}/audit-logs/flat/ --recursive

# Webhook Lambda logs
aws logs tail /aws/lambda/notion-webhook-handler --follow

# Importer Lambda logs
aws logs tail /aws/lambda/notion-s3-to-notion-importer --follow
```

### Security

- Authentication via Webhook Secret
- S3 bucket is private (all public access blocked)
- Versioning enabled
- 7-year log retention (configurable)
- Notion API Key / Slack Webhook URL masked with NoEcho

### Cost Estimate

- Lambda: Nearly free (within free tier)
- S3: Less than $0.01/month (at 100 events/day)
- Athena: Less than $1/month
- SNS (email notification): Nearly free

Total: Approximately $1-$2/month (Notion integration only)

### Cleanup

```bash
sam delete
aws s3 rb s3://notion-audit-logs-{AccountId} --force
```

### License

MIT License

### References

- [Notion API Documentation](https://developers.notion.com/)
- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [Athena JSON SerDe](https://docs.aws.amazon.com/athena/latest/ug/json-serde.html)
