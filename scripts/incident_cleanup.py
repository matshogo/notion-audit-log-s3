#!/usr/bin/env python3
"""2026-07 の自己イベントループで生成された S3 オブジェクトの削除と、
Lambda の CloudWatch Logs 保持期間の設定を行う運用スクリプト。

デフォルトは dry-run で、削除対象の件数・サイズを表示するだけで何も変更しない。
実際に反映するには --execute を付ける。

使い方:
    python3 scripts/incident_cleanup.py                  # dry-run（削除対象の確認のみ）
    python3 scripts/incident_cleanup.py --execute        # S3削除 + ログ保持1日を実際に反映
    python3 scripts/incident_cleanup.py --start 2026-07-08 --end 2026-07-19 --execute
    python3 scripts/incident_cleanup.py --bucket my-bucket --retention-days 1 --execute

前提: boto3 と、対象アカウントへの認証情報（AWS_PROFILE など）
"""

import argparse
import sys
from datetime import date, datetime, timedelta

import boto3

LOG_GROUPS = [
    '/aws/lambda/notion-webhook-handler',
    '/aws/lambda/notion-s3-to-notion-importer',
]

# バケットはバージョニング有効のため、通常の削除では容量が減らない。
# 全バージョン + 削除マーカーを明示的に消す必要がある。
PREFIX_TEMPLATES = [
    'audit-logs/original/{y}/{m}/{d}/',
    'audit-logs/flat/{y}/{m}/{d}/',
]

BATCH_SIZE = 1000  # delete_objects の上限


def date_range(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def collect_versions(s3, bucket: str, prefix: str):
    """prefix配下の全バージョンと削除マーカーを (Key, VersionId, Size) で列挙する"""
    paginator = s3.get_paginator('list_object_versions')
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for v in page.get('Versions', []):
            yield {'Key': v['Key'], 'VersionId': v['VersionId']}, v.get('Size', 0)
        for m in page.get('DeleteMarkers', []):
            yield {'Key': m['Key'], 'VersionId': m['VersionId']}, 0


def delete_batch(s3, bucket: str, objects: list) -> int:
    resp = s3.delete_objects(Bucket=bucket, Delete={'Objects': objects, 'Quiet': True})
    errors = resp.get('Errors', [])
    for e in errors:
        print(f"  [ERROR] {e.get('Key')} ({e.get('VersionId')}): {e.get('Message')}")
    return len(objects) - len(errors)


def cleanup_s3(s3, bucket: str, start: date, end: date, execute: bool) -> None:
    total_count = 0
    total_bytes = 0
    deleted = 0
    batch = []

    print(f"バケット: {bucket}")
    print(f"対象期間: {start} 〜 {end}")
    print(f"モード: {'削除実行' if execute else 'dry-run（削除しない）'}")
    print()

    for d in date_range(start, end):
        day_count = 0
        day_bytes = 0
        for tmpl in PREFIX_TEMPLATES:
            prefix = tmpl.format(y=d.strftime('%Y'), m=d.strftime('%m'), d=d.strftime('%d'))
            for obj, size in collect_versions(s3, bucket, prefix):
                day_count += 1
                day_bytes += size
                if execute:
                    batch.append(obj)
                    if len(batch) >= BATCH_SIZE:
                        deleted += delete_batch(s3, bucket, batch)
                        batch = []
        if day_count:
            print(f"  {d}: {day_count:>8,} 件 / {day_bytes / 1024 / 1024:,.1f} MB")
        total_count += day_count
        total_bytes += day_bytes

    if execute and batch:
        deleted += delete_batch(s3, bucket, batch)

    print()
    print(f"合計: {total_count:,} 件（バージョン・削除マーカー含む） / {total_bytes / 1024 / 1024:,.1f} MB")
    if execute:
        print(f"削除完了: {deleted:,} 件")
    else:
        print("dry-run のため削除していません。--execute を付けると削除します。")


def set_log_retention(logs, retention_days: int, execute: bool) -> None:
    print()
    print(f"CloudWatch Logs 保持期間: {retention_days} 日 {'（設定実行）' if execute else '（dry-run）'}")
    for group in LOG_GROUPS:
        if not execute:
            print(f"  {group}: 設定予定")
            continue
        try:
            logs.put_retention_policy(logGroupName=group, retentionInDays=retention_days)
            print(f"  {group}: 設定完了")
        except logs.exceptions.ResourceNotFoundException:
            print(f"  {group}: ロググループが存在しないためスキップ")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--bucket', help='対象バケット名（省略時: notion-audit-logs-<account-id>）')
    parser.add_argument('--start', default='2026-07-08', help='削除対象の開始日 YYYY-MM-DD（既定: 2026-07-08 = ループ開始日）')
    parser.add_argument('--end', default=date.today().isoformat(), help='削除対象の終了日 YYYY-MM-DD（既定: 今日）')
    parser.add_argument('--retention-days', type=int, default=1, help='CloudWatch Logs の保持日数（既定: 1）')
    parser.add_argument('--skip-s3', action='store_true', help='S3クリーンアップをスキップ')
    parser.add_argument('--skip-logs', action='store_true', help='ログ保持期間の設定をスキップ')
    parser.add_argument('--execute', action='store_true', help='実際に削除・設定を行う（省略時は dry-run）')
    args = parser.parse_args()

    start = datetime.strptime(args.start, '%Y-%m-%d').date()
    end = datetime.strptime(args.end, '%Y-%m-%d').date()
    if start > end:
        print('開始日が終了日より後になっています', file=sys.stderr)
        return 1

    bucket = args.bucket
    if not bucket:
        account = boto3.client('sts').get_caller_identity()['Account']
        bucket = f'notion-audit-logs-{account}'

    if not args.skip_s3:
        cleanup_s3(boto3.client('s3'), bucket, start, end, args.execute)
    if not args.skip_logs:
        set_log_retention(boto3.client('logs'), args.retention_days, args.execute)
    return 0


if __name__ == '__main__':
    sys.exit(main())
