#!/usr/bin/env python3
"""
S3に保存済みのAudit Log（flat JSON）をNotionデータベースに一括インポートするスクリプト

使い方:
  python3 import_s3_to_notion.py \
    --bucket notion-audit-logs-123456789012 \
    --notion-api-key ntn_xxxxx \
    --database-id xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

オプション:
  --prefix  S3のプレフィックス（デフォルト: audit-logs/flat/）
  --limit   インポート件数の上限（デフォルト: 全件）
"""

import argparse
import json
import time
import boto3
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


NOTION_API_URL = 'https://api.notion.com/v1/pages'
NOTION_VERSION = '2022-06-28'
# Notion APIレートリミット: 3リクエスト/秒
REQUEST_INTERVAL = 0.35


def build_notion_properties(record: dict) -> dict:
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


def write_to_notion(record: dict, api_key: str, database_id: str) -> bool:
    payload = json.dumps({
        'parent': {'database_id': database_id},
        'properties': build_notion_properties(record),
    }, ensure_ascii=False).encode('utf-8')

    req = Request(
        NOTION_API_URL,
        data=payload,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'Notion-Version': NOTION_VERSION,
        },
    )
    try:
        urlopen(req, timeout=15)
        return True
    except HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f"  HTTPError {e.code}: {body[:200]}")
        return False
    except URLError as e:
        print(f"  URLError: {e.reason}")
        return False


def main():
    parser = argparse.ArgumentParser(description='S3 Audit LogをNotionデータベースにインポート')
    parser.add_argument('--bucket', required=True, help='S3バケット名')
    parser.add_argument('--notion-api-key', required=True, help='Notion Internal Integration Token')
    parser.add_argument('--database-id', required=True, help='NotionデータベースID')
    parser.add_argument('--prefix', default='audit-logs/flat/', help='S3プレフィックス')
    parser.add_argument('--limit', type=int, default=0, help='インポート件数上限（0=全件）')
    args = parser.parse_args()

    s3 = boto3.client('s3')
    paginator = s3.get_paginator('list_objects_v2')

    total = 0
    success = 0
    errors = 0

    print(f"S3バケット: {args.bucket}")
    print(f"プレフィックス: {args.prefix}")
    print(f"Notionデータベース: {args.database_id}")
    print("---")

    for page in paginator.paginate(Bucket=args.bucket, Prefix=args.prefix):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if not key.endswith('.json'):
                continue

            try:
                resp = s3.get_object(Bucket=args.bucket, Key=key)
                body = resp['Body'].read().decode('utf-8').strip()
                if not body:
                    continue
                record = json.loads(body)
            except Exception as e:
                print(f"[SKIP] {key}: {e}")
                errors += 1
                continue

            total += 1
            event_id = record.get('event_id', '?')
            event_type = record.get('event_type', '?')

            if write_to_notion(record, args.notion_api_key, args.database_id):
                success += 1
                print(f"[OK] {total}: {event_type} ({event_id})")
            else:
                errors += 1
                print(f"[NG] {total}: {event_type} ({event_id})")

            # レートリミット対策
            time.sleep(REQUEST_INTERVAL)

            if args.limit and total >= args.limit:
                print(f"\n上限 {args.limit} 件に達しました")
                break
        else:
            continue
        break

    print(f"\n=== 完了 ===")
    print(f"合計: {total}件 / 成功: {success}件 / 失敗: {errors}件")


if __name__ == '__main__':
    main()
