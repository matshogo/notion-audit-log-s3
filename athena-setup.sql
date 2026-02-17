-- ============================================
-- Athena セットアップ用SQL
-- ============================================
-- 注意: Athenaは一度に1つのSQL文しか実行できません
-- 以下のSQL文を順番に1つずつ実行してください
-- ============================================

-- ステップ1: データベース作成
CREATE DATABASE IF NOT EXISTS notion_audit_logs;

-- ステップ2: 既存テーブルを削除（既に作成済みの場合）
DROP TABLE IF EXISTS notion_audit_logs.events_flat;

-- ステップ3: 平坦化されたデータ用のテーブルを作成
-- 注意: {YourAccountId} を実際のAWSアカウントIDに置き換えてください
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
LOCATION 's3://notion-audit-logs-{YourAccountId}/audit-logs/flat/';

-- ステップ4: データ件数を確認
SELECT COUNT(*) FROM notion_audit_logs.events_flat;

-- ステップ5: データの内容を確認
SELECT * FROM notion_audit_logs.events_flat LIMIT 10;
