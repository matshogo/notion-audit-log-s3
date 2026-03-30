#!/bin/bash
set -e

# ============================================
# Notion Audit Log to S3 デプロイスクリプト
# ============================================
# 使い方: ./deploy.sh

STACK_NAME="notion-audit-log-s3"
REGION="ap-northeast-1"

# --- 必須パラメータ ---
read -rp "WebhookSecret (空でもOK): " WEBHOOK_SECRET
read -rp "NotionApiKey: " NOTION_API_KEY
read -rp "NotionDatabaseId: " NOTION_DATABASE_ID

# --- 通知設定 ---
echo ""
echo "通知タイプを選択してください:"
echo "  1) none  - 通知なし"
echo "  2) email - メール通知"
echo "  3) slack - Slack通知"
read -rp "選択 [1]: " NOTIF_CHOICE

case "${NOTIF_CHOICE}" in
  2)
    NOTIFICATION_TYPE="email"
    read -rp "通知先メールアドレス: " NOTIFICATION_EMAIL
    SLACK_WEBHOOK_URL=""
    ;;
  3)
    NOTIFICATION_TYPE="slack"
    NOTIFICATION_EMAIL=""
    read -rp "Slack Webhook URL: " SLACK_WEBHOOK_URL
    ;;
  *)
    NOTIFICATION_TYPE="none"
    NOTIFICATION_EMAIL=""
    SLACK_WEBHOOK_URL=""
    ;;
esac

# --- ビルド ---
echo ""
echo "=== ビルド中... ==="
sam build

# --- デプロイ ---
echo ""
echo "=== デプロイ中... ==="
sam deploy \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --no-confirm-changeset \
  --parameter-overrides \
    "WebhookSecret='${WEBHOOK_SECRET}'" \
    "NotificationType='${NOTIFICATION_TYPE}'" \
    "NotificationEmail='${NOTIFICATION_EMAIL}'" \
    "SlackWebhookUrl='${SLACK_WEBHOOK_URL}'" \
    "NotionApiKey='${NOTION_API_KEY}'" \
    "NotionDatabaseId='${NOTION_DATABASE_ID}'"

echo ""
echo "=== デプロイ完了 ==="
echo "Webhook URLを確認:"
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`WebhookUrl`].OutputValue' \
  --output text
