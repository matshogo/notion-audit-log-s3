"""
S3に保存済みのAudit Log（flat JSON）をNotionデータベースに一括インポートするLambda

重複排除: Notionデータベースに既存のイベントIDを取得し、スキップする
ログレベル: IMPORT_LOG_LEVEL環境変数で全件/ページ公開のみを切り替え

手動実行用イベント例:
  {} （全件インポート）
  {"limit": 10} （10件だけ）
  {"prefix": "audit-logs/flat/2026/03/"} （特定月のみ）
"""

import json
import time
import os
import boto3
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from typing import Dict, Any, Set

s3_client = boto3.client('s3')

BUCKET_NAME = os.environ['BUCKET_NAME']
NOTION_API_KEY = os.environ.get('NOTION_API_KEY', '')
NOTION_DATABASE_ID = os.environ.get('NOTION_DATABASE_ID', '')
IMPORT_LOG_LEVEL = os.environ.get('IMPORT_LOG_LEVEL', 'all')
NOTION_API_BASE = 'https://api.notion.com/v1'
NOTION_VERSION = '2022-06-28'
REQUEST_INTERVAL = 0.35

PAGE_PUBLISH_EVENT_TYPES = {
    'page.published',
    'page.created',
    'page.content_updated.published',
}


def notion_request(method: str, url: str, data: dict = None) -> dict:
    """Notion APIへのリクエストを送信する"""
    payload = json.dumps(data, ensure_ascii=False).encode('utf-8') if data else None
    req = Request(
        url,
        data=payload,
        headers={
            'Authorization': f'Bearer {NOTION_API_KEY}',
            'Content-Type': 'application/json',
            'Notion-Version': NOTION_VERSION,
        },
        method=method,
    )
    resp = urlopen(req, timeout=15)
    return json.loads(resp.read().decode('utf-8'))


def fetch_existing_event_ids() -> Set[str]:
    """Notionデータベースから既存のイベントIDを全件取得する（重複排除用）"""
    event_ids = set()
    has_more = True
    start_cursor = None

    while has_more:
        body = {}
        if start_cursor:
            body['start_cursor'] = start_cursor

        try:
            result = notion_request(
                'POST',
                f'{NOTION_API_BASE}/databases/{NOTION_DATABASE_ID}/query',
                body,
            )
        except (HTTPError, URLError) as e:
            print(f"Notion DB query error: {e}")
            break

        for page in result.get('results', []):
            title_prop = page.get('properties', {}).get('イベントID', {})
            title_list = title_prop.get('title', [])
            if title_list:
                event_id = title_list[0].get('text', {}).get('content', '')
                if event_id:
                    event_ids.add(event_id)

        has_more = result.get('has_more', False)
        start_cursor = result.get('next_cursor')
        time.sleep(REQUEST_INTERVAL)

    print(f"Notion DB既存イベント数: {len(event_ids)}")
    return event_ids


def should_import(record: Dict[str, Any]) -> bool:
    """ログレベルに基づいてインポート対象かどうかを判定する"""
    if IMPORT_LOG_LEVEL == 'page_publish_only':
        event_type = record.get('event_type', '')
        return event_type in PAGE_PUBLISH_EVENT_TYPES
    return True


def build_notion_properties(record: Dict[str, Any]) -> dict:
    properties = {
        'イベントID': {'title': [{'text': {'content': record.get('event_id', '') or ''}}]},
        'イベントタイプ': {'select': {'name': record.get('event_type', 'unknown') or 'unknown'}},
        'ワークスペース': {'rich_text': [{'text': {'content': record.get('workspace_name', '') or ''}}]},
        'プラットフォーム': {'select': {'name': record.get('platform', 'unknown') or 'unknown'}},
        'IPアドレス': {'rich_text': [{'text': {'content': record.get('ip_address', '') or ''}}]},
    }

    if record.get('user_email'):
        properties['ユーザー'] = {'email': record['user_email']}
    else:
        properties['ユーザー'] = {'rich_text': [{'text': {'content': '不明'}}]}

    if record.get('event_timestamp'):
        properties['日時'] = {'date': {'start': record['event_timestamp']}}

    return properties


def write_to_notion(record: Dict[str, Any]) -> bool:
    payload = {
        'parent': {'database_id': NOTION_DATABASE_ID},
        'properties': build_notion_properties(record),
    }
    try:
        notion_request('POST', f'{NOTION_API_BASE}/pages', payload)
        return True
    except HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f"  HTTPError {e.code}: {body[:200]}")
        return False
    except URLError as e:
        print(f"  URLError: {e.reason}")
        return False


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        return {'statusCode': 400, 'body': 'NOTION_API_KEY and NOTION_DATABASE_ID are required'}

    prefix = event.get('prefix', 'audit-logs/flat/')
    limit = event.get('limit', 0)

    print(f"ImportLogLevel: {IMPORT_LOG_LEVEL}")
    print("重複排除用にNotion DBの既存イベントIDを取得中...")
    existing_ids = fetch_existing_event_ids()

    paginator = s3_client.get_paginator('list_objects_v2')
    total = 0
    success = 0
    skipped_dup = 0
    skipped_filter = 0
    errors = 0

    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if not key.endswith('.json'):
                continue

            # Lambdaタイムアウト対策: 残り30秒を切ったら中断
            remaining = context.get_remaining_time_in_millis() if context else 999999
            if remaining < 30000:
                print(f"タイムアウト間近のため中断 (残り{remaining}ms)")
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'タイムアウト間近のため中断',
                        'total': total, 'success': success,
                        'skipped_dup': skipped_dup, 'skipped_filter': skipped_filter,
                        'errors': errors,
                        'last_key': key,
                    })
                }

            try:
                resp = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
                body = resp['Body'].read().decode('utf-8').strip()
                if not body:
                    continue
                record = json.loads(body)
            except Exception as e:
                print(f"[SKIP] {key}: {e}")
                errors += 1
                continue

            event_id = record.get('event_id', '')

            # 重複排除
            if event_id and event_id in existing_ids:
                skipped_dup += 1
                continue

            # ログレベルフィルタ
            if not should_import(record):
                skipped_filter += 1
                continue

            total += 1
            if write_to_notion(record):
                success += 1
                existing_ids.add(event_id)
                print(f"[OK] {total}: {record.get('event_type')} ({event_id})")
            else:
                errors += 1
                print(f"[NG] {total}: {record.get('event_type')} ({event_id})")

            time.sleep(REQUEST_INTERVAL)

            if limit and total >= limit:
                break
        else:
            continue
        break

    result = {
        'message': 'インポート完了',
        'total': total, 'success': success,
        'skipped_dup': skipped_dup, 'skipped_filter': skipped_filter,
        'errors': errors,
    }
    print(f"=== 結果: {json.dumps(result, ensure_ascii=False)} ===")
    return {'statusCode': 200, 'body': json.dumps(result)}
