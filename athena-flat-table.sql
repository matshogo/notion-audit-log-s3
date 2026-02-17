-- ============================================
-- 平坦化されたJSONファイル用のテーブル
-- ============================================

-- ステップ1: 既存のテーブルとビューを削除
DROP TABLE IF EXISTS notion_audit_logs.events_flat;

-- ステップ2: 平坦化されたデータ用のテーブルを作成
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

-- ステップ3: データ確認
SELECT * FROM notion_audit_logs.events_flat LIMIT 10;

-- ステップ4: 件数確認
SELECT COUNT(*) FROM notion_audit_logs.events_flat;

-- ステップ5: イベントタイプ別の集計
SELECT event_type, COUNT(*) as count 
FROM notion_audit_logs.events_flat 
GROUP BY event_type 
ORDER BY count DESC;
