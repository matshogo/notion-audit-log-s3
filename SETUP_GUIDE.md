# セットアップガイド / Setup Guide

[日本語](#日本語) | [English](#english)

---

## 日本語

### 目次

1. [前提条件](#1-前提条件)
2. [Notion側の準備](#2-notion側の準備)
3. [AWSデプロイ](#3-awsデプロイ)
4. [Notion Webhookの設定](#4-notion-webhookの設定)
5. [S3→Notionインポート](#5-s3notionインポート)
6. [Athenaのセットアップ（オプション）](#6-athenaのセットアップオプション)
7. [トラブルシューティング](#7-トラブルシューティング)

---

### 1. 前提条件

- AWS CLI 設定済み
- AWS SAM CLI インストール済み
- Python 3.9以上
- Notion ワークスペースの管理者権限
- Notion Enterprise プラン（Custom SIEM Integration利用時）

---

### 2. Notion側の準備

#### 2-1. Internal Integrationの作成

1. [Notion Integrations](https://www.notion.so/my-integrations) にアクセス
2. 「New integration」をクリック
3. 名前を入力（例: `Audit Log Dashboard`）
4. 関連するワークスペースを選択
5. 「Submit」をクリック
6. 表示される「Internal Integration Secret」（`ntn_` で始まる文字列）を控える

#### 2-2. Notionデータベースの作成

Notionで新しいデータベース（フルページ）を作成し、以下のプロパティを設定してください：

| プロパティ名 | 型 | 説明 |
|---|---|---|
| イベントID | タイトル | Audit LogのイベントID |
| イベントタイプ | セレクト | イベントの種類（page.created等） |
| ユーザー | メール | 操作を行ったユーザーのメール |
| ワークスペース | テキスト | ワークスペース名 |
| プラットフォーム | セレクト | 利用プラットフォーム |
| IPアドレス | テキスト | アクセス元IPアドレス |
| 日時 | 日付 | イベント発生日時 |

#### 2-3. Integrationへのアクセス権付与

1. 作成したデータベースページを開く
2. 右上の「...」→「コネクト」→ 2-1で作成したIntegrationを選択
3. 「確認」をクリック

#### 2-4. データベースIDの取得

データベースのURLからIDを取得します：

```
https://www.notion.so/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx?v=yyyyyyyy
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                      この部分がデータベースID（32文字）
```

---

### 3. AWSデプロイ

#### 3-1. Webhook Secretの生成

```bash
openssl rand -base64 32
```

生成された文字列を安全に保管してください。

#### 3-2. デプロイスクリプトを使う場合

```bash
./deploy.sh
```

対話形式で各パラメータを入力します。

#### 3-3. 手動でデプロイする場合

```bash
sam build

sam deploy --stack-name notion-audit-log-s3 \
  --region ap-northeast-1 \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --parameter-overrides \
    WebhookSecret='生成したシークレット' \
    NotionApiKey='ntn_xxxxx' \
    NotionDatabaseId='xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \
    ImportLogLevel='all' \
    NotificationType='none'
```

#### パラメータの説明

- `ImportLogLevel`:
  - `all` — 全てのAudit LogイベントをNotionデータベースに取り込む
  - `page_publish_only` — ページ公開関連イベントのみ取り込む（`page.published`, `page.created`, `page.content_updated.published`）

- `NotificationType`:
  - `none` — 通知なし
  - `email` — ページ公開時にメール通知（`NotificationEmail` の指定が必要）
  - `slack` — ページ公開時にSlack通知（`SlackWebhookUrl` の指定が必要）

#### 3-4. デプロイ結果の確認

デプロイ完了後、以下が出力されます：

```
WebhookUrl:         https://xxxxx.execute-api.ap-northeast-1.amazonaws.com/prod/webhook
BucketName:         notion-audit-logs-{AccountId}
FunctionName:       notion-webhook-handler
ImportFunctionName: notion-s3-to-notion-importer
```

`WebhookUrl` を控えてください。

---

### 4. Notion Webhookの設定

> この機能はNotion Enterpriseプランで利用可能です。

1. Notion Workspace Settings → Integrations → Custom SIEM Integration
2. 以下を設定：
   - Webhook URL: デプロイで取得したURL
   - Webhook headers:
     - Header name: `x-notion-webhook-secret`
     - Header value: 生成したWebhookSecret
3. 「Save」をクリック

#### 動作確認

Notionで何かアクション（ページ作成など）を実行後：

```bash
# S3にログが保存されているか確認
aws s3 ls s3://notion-audit-logs-{AccountId}/audit-logs/flat/ --recursive
```

---

### 5. S3→Notionインポート

S3に既に保存されているAudit LogをNotionデータベースに一括インポートできます。
重複排除機能があるため、同じイベントが二重に取り込まれることはありません。

#### 手動実行

```bash
# 全件インポート
aws lambda invoke --function-name notion-s3-to-notion-importer \
  --payload '{}' --cli-binary-format raw-in-base64-out output.json

# テスト（10件だけ）
aws lambda invoke --function-name notion-s3-to-notion-importer \
  --payload '{"limit": 10}' --cli-binary-format raw-in-base64-out output.json

# 特定月のみ
aws lambda invoke --function-name notion-s3-to-notion-importer \
  --payload '{"prefix": "audit-logs/flat/2026/03/"}' --cli-binary-format raw-in-base64-out output.json
```

#### 定期実行の有効化

template.yaml の `S3ToNotionImportFunction` の `Enabled` を `true` に変更して再デプロイすると、6時間ごとに自動実行されます。

```yaml
Events:
  ScheduledImport:
    Type: Schedule
    Properties:
      Schedule: rate(6 hours)
      Enabled: true   # ← false から true に変更
```

#### ページ公開時の即時実行

ページ公開イベント（`page.published`, `page.created`, `page.content_updated.published`）を検知すると、Webhook Lambda がインポートLambdaを非同期で即時実行します。この動作はデフォルトで有効です。

#### ローカルスクリプトでのインポート

Lambda を使わずローカルから実行することもできます：

```bash
python3 import_s3_to_notion.py \
  --bucket 'notion-audit-logs-{AccountId}' \
  --notion-api-key 'ntn_xxxxx' \
  --database-id 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \
  --limit 10
```

---

### 6. Athenaのセットアップ（オプション）

S3上のデータをSQLでクエリしたい場合に設定します。

#### 6-1. クエリ結果保存用バケットの作成

```bash
aws s3 mb s3://aws-athena-query-results-{AccountId}-{Region}
```

#### 6-2. Athenaコンソールでの設定

1. AWSコンソールで Athena を開く
2. Settings → Manage → Query result location に上記バケットを設定

#### 6-3. データベースとテーブルの作成

```sql
CREATE DATABASE IF NOT EXISTS notion_audit_logs;
```

```sql
CREATE EXTERNAL TABLE notion_audit_logs.events_flat (
  event_id string,
  event_timestamp string,
  workspace_id string,
  workspace_name string,
  ip_address string,
  platform string,
  event_type string,
  user_email string,
  actor_id string,
  actor_type string,
  raw_event string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://notion-audit-logs-{AccountId}/audit-logs/flat/';
```

`{AccountId}` を実際のAWSアカウントIDに置き換えてください。

#### 6-4. 動作確認

```sql
SELECT COUNT(*) FROM notion_audit_logs.events_flat;
SELECT * FROM notion_audit_logs.events_flat LIMIT 10;
```

---

### 7. トラブルシューティング

#### S3にログが保存されない

- Webhook URLが正しいか確認
- `x-notion-webhook-secret` ヘッダーの値がデプロイ時のSecretと一致するか確認
- Lambda のログを確認: `aws logs tail /aws/lambda/notion-webhook-handler --follow`

#### Notionデータベースに書き込まれない

- `NotionApiKey` と `NotionDatabaseId` が正しく設定されているか確認
- IntegrationにデータベースへのアクセスPermissionが付与されているか確認
- インポートLambdaのログを確認: `aws logs tail /aws/lambda/notion-s3-to-notion-importer --follow`

#### 重複データが入ってしまった

- インポートLambdaは実行時にNotionデータベースの既存イベントIDを取得して重複排除します
- Webhook Lambda のリアルタイム書き込みとインポートLambdaが同時に動くと稀に重複する可能性があります
- Notionデータベース上でイベントIDでソートし、手動で重複を削除してください

#### 通知が届かない

- `NotificationType` が正しく設定されているか確認
- Email の場合: SNSサブスクリプションの確認メールを承認したか確認
- Slack の場合: Incoming Webhook URLが有効か確認

---
---

## English

### Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Notion Preparation](#2-notion-preparation)
3. [AWS Deployment](#3-aws-deployment)
4. [Notion Webhook Configuration](#4-notion-webhook-configuration)
5. [S3 → Notion Import](#5-s3--notion-import)
6. [Athena Setup (Optional)](#6-athena-setup-optional)
7. [Troubleshooting](#7-troubleshooting-1)

---

### 1. Prerequisites

- AWS CLI configured
- AWS SAM CLI installed
- Python 3.9 or later
- Notion workspace admin access
- Notion Enterprise plan (for Custom SIEM Integration)

---

### 2. Notion Preparation

#### 2-1. Create an Internal Integration

1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Click "New integration"
3. Enter a name (e.g., `Audit Log Dashboard`)
4. Select the associated workspace
5. Click "Submit"
6. Copy the "Internal Integration Secret" (starts with `ntn_`)

#### 2-2. Create a Notion Database

Create a new full-page database in Notion with the following properties:

| Property Name | Type | Description |
|---|---|---|
| イベントID | Title | Audit Log event ID |
| イベントタイプ | Select | Event type (e.g., page.created) |
| ユーザー | Email | Email of the user who performed the action |
| ワークスペース | Text | Workspace name |
| プラットフォーム | Select | Platform used |
| IPアドレス | Text | Source IP address |
| 日時 | Date | Event timestamp |

#### 2-3. Grant Integration Access

1. Open the database page
2. Click "..." → "Connections" → Select the integration created in 2-1
3. Click "Confirm"

#### 2-4. Get the Database ID

Extract the ID from the database URL:

```
https://www.notion.so/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx?v=yyyyyyyy
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                      This part is the database ID (32 characters)
```

---

### 3. AWS Deployment

#### 3-1. Generate a Webhook Secret

```bash
openssl rand -base64 32
```

Store the generated string securely.

#### 3-2. Using the Deploy Script

```bash
./deploy.sh
```

You will be prompted to enter each parameter interactively.

#### 3-3. Manual Deployment

```bash
sam build

sam deploy --stack-name notion-audit-log-s3 \
  --region ap-northeast-1 \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --parameter-overrides \
    WebhookSecret='your-generated-secret' \
    NotionApiKey='ntn_xxxxx' \
    NotionDatabaseId='xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \
    ImportLogLevel='all' \
    NotificationType='none'
```

#### Parameter Details

- `ImportLogLevel`:
  - `all` — Import all Audit Log events to the Notion database
  - `page_publish_only` — Import only page publish events (`page.published`, `page.created`, `page.content_updated.published`)

- `NotificationType`:
  - `none` — No notifications
  - `email` — Email notification on page publish (`NotificationEmail` required)
  - `slack` — Slack notification on page publish (`SlackWebhookUrl` required)

#### 3-4. Verify Deployment

After deployment, the following outputs are displayed:

```
WebhookUrl:         https://xxxxx.execute-api.ap-northeast-1.amazonaws.com/prod/webhook
BucketName:         notion-audit-logs-{AccountId}
FunctionName:       notion-webhook-handler
ImportFunctionName: notion-s3-to-notion-importer
```

Note the `WebhookUrl` for the next step.

---

### 4. Notion Webhook Configuration

> This feature is available on the Notion Enterprise plan.

1. Go to Notion Workspace Settings → Integrations → Custom SIEM Integration
2. Configure:
   - Webhook URL: The URL from deployment output
   - Webhook headers:
     - Header name: `x-notion-webhook-secret`
     - Header value: Your generated WebhookSecret
3. Click "Save"

#### Verify

After performing an action in Notion (e.g., creating a page):

```bash
aws s3 ls s3://notion-audit-logs-{AccountId}/audit-logs/flat/ --recursive
```

---

### 5. S3 → Notion Import

You can bulk import existing Audit Logs from S3 into the Notion database.
The deduplication feature prevents the same event from being imported twice.

#### Manual Execution

```bash
# Import all records
aws lambda invoke --function-name notion-s3-to-notion-importer \
  --payload '{}' --cli-binary-format raw-in-base64-out output.json

# Test with 10 records
aws lambda invoke --function-name notion-s3-to-notion-importer \
  --payload '{"limit": 10}' --cli-binary-format raw-in-base64-out output.json

# Specific month only
aws lambda invoke --function-name notion-s3-to-notion-importer \
  --payload '{"prefix": "audit-logs/flat/2026/03/"}' --cli-binary-format raw-in-base64-out output.json
```

#### Enable Scheduled Execution

Change `Enabled` to `true` in the `S3ToNotionImportFunction` section of template.yaml and redeploy to run automatically every 6 hours.

```yaml
Events:
  ScheduledImport:
    Type: Schedule
    Properties:
      Schedule: rate(6 hours)
      Enabled: true   # ← Change from false to true
```

#### Immediate Execution on Page Publish

When a page publish event (`page.published`, `page.created`, `page.content_updated.published`) is detected, the Webhook Lambda asynchronously triggers the importer Lambda. This behavior is enabled by default.

#### Local Script Import

You can also run the import from your local machine without Lambda:

```bash
python3 import_s3_to_notion.py \
  --bucket 'notion-audit-logs-{AccountId}' \
  --notion-api-key 'ntn_xxxxx' \
  --database-id 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \
  --limit 10
```

---

### 6. Athena Setup (Optional)

Set this up if you want to query S3 data with SQL.

#### 6-1. Create a Query Results Bucket

```bash
aws s3 mb s3://aws-athena-query-results-{AccountId}-{Region}
```

#### 6-2. Configure Athena Console

1. Open Athena in the AWS Console
2. Settings → Manage → Set Query result location to the bucket above

#### 6-3. Create Database and Table

```sql
CREATE DATABASE IF NOT EXISTS notion_audit_logs;
```

```sql
CREATE EXTERNAL TABLE notion_audit_logs.events_flat (
  event_id string,
  event_timestamp string,
  workspace_id string,
  workspace_name string,
  ip_address string,
  platform string,
  event_type string,
  user_email string,
  actor_id string,
  actor_type string,
  raw_event string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://notion-audit-logs-{AccountId}/audit-logs/flat/';
```

Replace `{AccountId}` with your actual AWS account ID.

#### 6-4. Verify

```sql
SELECT COUNT(*) FROM notion_audit_logs.events_flat;
SELECT * FROM notion_audit_logs.events_flat LIMIT 10;
```

---

### 7. Troubleshooting

#### Logs are not saved to S3

- Verify the Webhook URL is correct
- Verify the `x-notion-webhook-secret` header value matches the deployed Secret
- Check Lambda logs: `aws logs tail /aws/lambda/notion-webhook-handler --follow`

#### Data is not written to the Notion database

- Verify `NotionApiKey` and `NotionDatabaseId` are correctly configured
- Verify the Integration has access permission to the database
- Check importer Lambda logs: `aws logs tail /aws/lambda/notion-s3-to-notion-importer --follow`

#### Duplicate data appeared

- The importer Lambda fetches existing event IDs from the Notion database for deduplication on each run
- Rare duplicates may occur if the Webhook Lambda's real-time write and the importer Lambda run simultaneously
- Sort by event ID in the Notion database and manually remove duplicates

#### Notifications are not delivered

- Verify `NotificationType` is correctly set
- For email: Confirm you approved the SNS subscription confirmation email
- For Slack: Verify the Incoming Webhook URL is valid
