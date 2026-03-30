import json
import boto3
import os
from datetime import datetime
from typing import Dict, Any
from urllib.request import Request, urlopen
from urllib.error import URLError

s3_client = boto3.client('s3')
sns_client = boto3.client('sns')
lambda_client = boto3.client('lambda')

BUCKET_NAME = os.environ['BUCKET_NAME']
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', '')
NOTIFICATION_TYPE = os.environ.get('NOTIFICATION_TYPE', 'none')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', '')
SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL', '')
NOTION_API_KEY = os.environ.get('NOTION_API_KEY', '')
NOTION_DATABASE_ID = os.environ.get('NOTION_DATABASE_ID', '')
IMPORT_FUNCTION_NAME = os.environ.get('IMPORT_FUNCTION_NAME', '')
IMPORT_LOG_LEVEL = os.environ.get('IMPORT_LOG_LEVEL', 'all')

# 通知対象のイベントタイプ
PAGE_PUBLISH_EVENT_TYPES = {
    'page.published',
    'page.created',
    'page.content_updated.published',
}


def flatten_event(audit_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    NotionのイベントデータをAthena/QuickSight用に平坦化
    """
    event = audit_data.get('event', {})
    
    # 基本フィールド
    flattened = {
        'event_id': event.get('id'),
        'event_timestamp': event.get('timestamp'),
        'workspace_id': event.get('workspace_id'),
        'workspace_name': event.get('workspace_name'),
        'ip_address': event.get('ip_address'),
        'platform': event.get('platform'),
        'event_type': event.get('type'),
    }
    
    # アクター情報
    actor = event.get('actor', {})
    person = actor.get('person', {})
    flattened['user_email'] = person.get('email')
    flattened['actor_id'] = actor.get('id')
    flattened['actor_type'] = actor.get('type')
    
    # 元のJSONも保存（詳細分析用）
    flattened['raw_event'] = json.dumps(event, ensure_ascii=False)
    
    return flattened


def send_notification(flattened_data: Dict[str, Any]) -> None:
    """
    ページ公開イベントの通知を送信する
    """
    event_type = flattened_data.get('event_type', '')
    if event_type not in PAGE_PUBLISH_EVENT_TYPES:
        return
    if NOTIFICATION_TYPE == 'none':
        return

    user = flattened_data.get('user_email', '不明')
    workspace = flattened_data.get('workspace_name', '不明')
    timestamp = flattened_data.get('event_timestamp', '')
    subject = f"[Notion] ページが公開されました ({event_type})"
    message = (
        f"イベント: {event_type}\n"
        f"ユーザー: {user}\n"
        f"ワークスペース: {workspace}\n"
        f"日時: {timestamp}"
    )

    try:
        if NOTIFICATION_TYPE == 'email' and SNS_TOPIC_ARN:
            sns_client.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=subject,
                Message=message,
            )
            print(f"Email notification sent for {event_type}")

        elif NOTIFICATION_TYPE == 'slack' and SLACK_WEBHOOK_URL:
            payload = json.dumps({
                'text': f":mega: *{subject}*\n{message}"
            }).encode('utf-8')
            req = Request(
                SLACK_WEBHOOK_URL,
                data=payload,
                headers={'Content-Type': 'application/json'},
            )
            urlopen(req, timeout=5)
            print(f"Slack notification sent for {event_type}")

    except (URLError, Exception) as e:
        # 通知失敗はログに残すが、メイン処理は止めない
        print(f"Notification error: {str(e)}")


def write_to_notion_db(flattened_data: Dict[str, Any]) -> None:
    """
    平坦化したイベントデータをNotionデータベースに書き込む
    """
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        return

    # ログレベルフィルタ
    if IMPORT_LOG_LEVEL == 'page_publish_only':
        event_type = flattened_data.get('event_type', '')
        if event_type not in PAGE_PUBLISH_EVENT_TYPES:
            return

    properties = {
        'イベントID': {'title': [{'text': {'content': flattened_data.get('event_id', '') or ''}}]},
        'イベントタイプ': {'select': {'name': flattened_data.get('event_type', 'unknown') or 'unknown'}},
        'ユーザー': {'email': flattened_data.get('user_email', '')} if flattened_data.get('user_email') else {'rich_text': [{'text': {'content': '不明'}}]},
        'ワークスペース': {'rich_text': [{'text': {'content': flattened_data.get('workspace_name', '') or ''}}]},
        'プラットフォーム': {'select': {'name': flattened_data.get('platform', 'unknown') or 'unknown'}},
        'IPアドレス': {'rich_text': [{'text': {'content': flattened_data.get('ip_address', '') or ''}}]},
    }

    # タイムスタンプがあればdate型で設定
    event_ts = flattened_data.get('event_timestamp')
    if event_ts:
        properties['日時'] = {'date': {'start': event_ts}}

    payload = json.dumps({
        'parent': {'database_id': NOTION_DATABASE_ID},
        'properties': properties,
    }, ensure_ascii=False).encode('utf-8')

    try:
        req = Request(
            'https://api.notion.com/v1/pages',
            data=payload,
            headers={
                'Authorization': f'Bearer {NOTION_API_KEY}',
                'Content-Type': 'application/json',
                'Notion-Version': '2022-06-28',
            },
        )
        urlopen(req, timeout=10)
        print(f"Written to Notion DB: {flattened_data.get('event_id')}")
    except (URLError, Exception) as e:
        # Notion書き込み失敗はログに残すが、メイン処理は止めない
        print(f"Notion DB write error: {str(e)}")


def trigger_import(flattened_data: Dict[str, Any]) -> None:
    """
    ページ公開イベント時にインポートLambdaを非同期で即時実行する
    """
    event_type = flattened_data.get('event_type', '')
    if event_type not in PAGE_PUBLISH_EVENT_TYPES:
        return
    if not IMPORT_FUNCTION_NAME:
        return

    try:
        lambda_client.invoke(
            FunctionName=IMPORT_FUNCTION_NAME,
            InvocationType='Event',  # 非同期呼び出し
            Payload=json.dumps({'trigger': 'page_publish', 'event_type': event_type}),
        )
        print(f"Triggered import Lambda for {event_type}")
    except Exception as e:
        print(f"Failed to trigger import Lambda: {str(e)}")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    NotionのWebhookを受け取り、Audit logをS3に保存する
    """
    try:
        # Webhook認証チェック
        if WEBHOOK_SECRET:
            headers = event.get('headers', {})
            # ヘッダー名は小文字に正規化される
            auth_header = headers.get('x-notion-webhook-secret', '')
            if auth_header != WEBHOOK_SECRET:
                return {
                    'statusCode': 401,
                    'body': json.dumps({'error': 'Unauthorized'})
                }
        
        # リクエストボディの取得
        body = event.get('body', '{}')
        if isinstance(body, str):
            audit_data = json.loads(body)
        else:
            audit_data = body
        
        # タイムスタンプ生成
        timestamp = datetime.utcnow()
        date_prefix = timestamp.strftime('%Y/%m/%d')
        filename = f"{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.json"
        
        # データを平坦化
        flattened_data = flatten_event(audit_data)
        
        # S3キーの生成（元のJSONと平坦化版の両方を保存）
        s3_key_original = f"audit-logs/original/{date_prefix}/{filename}"
        s3_key_flat = f"audit-logs/flat/{date_prefix}/{filename}"
        
        # 元のJSONを保存
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key_original,
            Body=json.dumps(audit_data, ensure_ascii=False, indent=2),
            ContentType='application/json'
        )
        
        # 平坦化したJSONを保存（1行JSON形式）
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key_flat,
            Body=json.dumps(flattened_data, ensure_ascii=False) + '\n',
            ContentType='application/json'
        )
        
        print(f"Successfully saved audit log to s3://{BUCKET_NAME}/{s3_key_flat}")
        
        # ページ公開イベントの場合は通知を送信
        send_notification(flattened_data)
        
        # Notionデータベースに書き込み（ダッシュボード用）
        write_to_notion_db(flattened_data)
        
        # ページ公開イベントの場合はインポートLambdaを即時実行
        trigger_import(flattened_data)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Audit log saved successfully',
                's3_key_original': s3_key_original,
                's3_key_flat': s3_key_flat
            })
        }
        
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid JSON'})
        }
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }
