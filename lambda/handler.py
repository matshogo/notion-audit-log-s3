import json
import boto3
import os
from datetime import datetime
from typing import Dict, Any

s3_client = boto3.client('s3')

BUCKET_NAME = os.environ['BUCKET_NAME']
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', '')


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
